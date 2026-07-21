/**
 * Cross-platform encrypted secret storage (Dev-Phase 1 D1-9).
 *
 * Per `analysis/09` §二 + specs/security-compliance/spec.md Requirement: API 密钥
 * MUST 通过 OS 原生 credential manager 加密存储. Uses @napi-rs/keyring as primary
 * (Windows Credential Manager / macOS Keychain / Linux Secret Service) with
 * Electron's built-in safeStorage as fallback when no secret service is
 * available (e.g., headless Linux CI).
 *
 * The fallback writes a `sddp-pet-secrets.json` file under app.getPath("userData")
 * encrypted via safeStorage (which uses DPAPI on Windows / Keychain on macOS /
 * libsecret on Linux). This file is gitignored and is a fallback ONLY —
 * `@napi-rs/keyring` is the primary path on dev/user machines.
 *
 * Public API (mirrors the keyring module shape):
 *   setPassword(service, account, password): Promise<void>
 *   getPassword(service, account): Promise<string | undefined>
 *   deletePassword(service, account): Promise<boolean>
 *   isUsingFallback(): boolean  — for diagnostic UI
 */

import { Entry } from "@napi-rs/keyring";
import { safeStorage, app } from "electron";
import * as fs from "node:fs";
import * as path from "node:path";

const SERVICE_DEFAULT = "sddp-pet";

// In-memory flag set on first fallback write
let _usingFallback = false;

interface FallbackStore {
  [service_account: string]: string; // base64-encoded encrypted buffer
}

function fallbackPath(): string {
  return path.join(app.getPath("userData"), "sddp-pet-secrets.json");
}

function readFallback(): FallbackStore {
  try {
    const raw = fs.readFileSync(fallbackPath(), "utf-8");
    return JSON.parse(raw) as FallbackStore;
  } catch {
    return {};
  }
}

function writeFallback(store: FallbackStore): void {
  const dir = path.dirname(fallbackPath());
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  // 0o600: owner read/write only — defense-in-depth; safeStorage is the real boundary
  fs.writeFileSync(fallbackPath(), JSON.stringify(store), { mode: 0o600 });
}

function fallbackKey(service: string, account: string): string {
  return `${service}::${account}`;
}

/**
 * Store a secret. Tries @napi-rs/keyring first; on any error, falls back to
 * safeStorage-encrypted local file.
 */
export async function setPassword(
  service: string,
  account: string,
  password: string,
): Promise<void> {
  try {
    const entry = new Entry(service, account);
    entry.setPassword(password);
    _usingFallback = false;
    return;
  } catch (err) {
    console.warn(
      `[secrets] @napi-rs/keyring failed (${(err as Error).message}); ` +
        `falling back to safeStorage file`,
    );
  }
  // Fallback: safeStorage
  if (!safeStorage.isEncryptionAvailable()) {
    throw new Error(
      "safeStorage encryption not available; cannot store secret. " +
        "Install a keychain/secret service or run on Windows/macOS.",
    );
  }
  const buf = safeStorage.encryptString(password);
  const store = readFallback();
  store[fallbackKey(service, account)] = buf.toString("base64");
  writeFallback(store);
  _usingFallback = true;
}

/**
 * Read a secret. Tries @napi-rs/keyring first; on miss/error, tries fallback.
 * Returns undefined if not found in either.
 */
export async function getPassword(
  service: string,
  account: string,
): Promise<string | undefined> {
  // Try keyring
  try {
    const entry = new Entry(service, account);
    const pw = entry.getPassword();
    if (pw !== null && pw !== undefined && pw.length > 0) {
      return pw;
    }
  } catch (err) {
    // ignore; try fallback
  }
  // Try fallback
  try {
    const store = readFallback();
    const b64 = store[fallbackKey(service, account)];
    if (!b64) return undefined;
    const buf = Buffer.from(b64, "base64");
    if (!safeStorage.isEncryptionAvailable()) return undefined;
    return safeStorage.decryptString(buf);
  } catch {
    return undefined;
  }
}

/**
 * Delete a secret from both stores. Returns true if anything was deleted.
 */
export async function deletePassword(
  service: string,
  account: string,
): Promise<boolean> {
  let deleted = false;
  try {
    const entry = new Entry(service, account);
    deleted = entry.deletePassword() || deleted;
  } catch {
    // ignore
  }
  try {
    const store = readFallback();
    const key = fallbackKey(service, account);
    if (key in store) {
      delete store[key];
      writeFallback(store);
      deleted = true;
    }
  } catch {
    // ignore
  }
  return deleted;
}

/** True if the most recent successful write used the safeStorage fallback. */
export function isUsingFallback(): boolean {
  return _usingFallback;
}

/** Convenience: set the API key for an LLM provider (OpenAI / DeepSeek / ...). */
export async function setApiKey(
  provider: string,
  key: string,
  service: string = SERVICE_DEFAULT,
): Promise<void> {
  await setPassword(service, `api-key-${provider}`, key);
}

export async function getApiKey(
  provider: string,
  service: string = SERVICE_DEFAULT,
): Promise<string | undefined> {
  return getPassword(service, `api-key-${provider}`);
}

export async function deleteApiKey(
  provider: string,
  service: string = SERVICE_DEFAULT,
): Promise<boolean> {
  return deletePassword(service, `api-key-${provider}`);
}
