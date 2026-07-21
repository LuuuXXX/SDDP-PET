# G9: 跨平台密钥存储与安全合规 (Dev-Phase 1 技术研究)

> 日期: 2026-07-21
> 状态: **P0 — Dev-Phase 1 前置** (D1-9/10/11/12/13 全部阻塞此文档)
> 关联:
> - `analysis/00-sddp-pet-final.md` §八(合规性要求)、§十三(缺失考虑标注)
> - `analysis/04-llm-provider-strategy.md` (provider 锁定 = OpenAI Tier-S + DeepSeek Tier-B 测试路径)
> - `analysis/03-crewai-version-strategy.md` §二(诚实声明风格)、§五(SafeAgent 是硬性前提)
> - `openspec/specs/development-roadmap/dod.md` Dev-Phase 1: D1-9 ~ D1-13

---

## 一、问题陈述

Dev-Phase 0 已交付"本地引擎 + 5 角色线性 + CLI"，但 API key 当前**仅来自环境变量**（见 `backend/sddp/cli/main.py:86` `use_mock = mock or not os.environ.get("OPENAI_API_KEY")`；`backend/scripts/deepseek-env.sh:30` `export OPENAI_API_KEY="$DEEPSEEK_API_KEY"`）。这对 MVP 验证够用，但 Dev-Phase 1 要交付 Electron 桌宠前端，五个安全合规 DoD 必须同时落地：

| DoD | 一句话 | 风险若不解决 |
|-----|--------|--------------|
| **D1-9** | API 密钥加密存储，明文不出现在磁盘 | 用户粘贴的 `sk-...` 落盘 → 全盘被 `grep` 抓到 → 密钥泄露 |
| **D1-10** | 首次启动隐私同意弹窗；拒绝则不启动流程 | 用户不知代码会发往 OpenAI → 法律/信任风险 |
| **D1-11** | 代码预过滤（本地脱敏）后再发远程 | 真实密钥/PII 直接进 LLM 上下文 → 二次泄露 |
| **D1-12** | 桌宠气泡旁标注"AI 驱动" | 用户误以为回复是本地确定性输出 → 误用 |
| **D1-13** | `OTEL_SDK_DISABLED=true` 硬编码 | OTEL OTLP 上报到默认 endpoint → 静默外发遥测 |

本文件锁定跨平台密钥存储库 + 给出 D1-9~D1-13 的具体实现路径与验证方法。**不**覆盖 D1-1~D1-8（前端窗口/穿透点击/WebSocket，属 10 号文档范畴）与 D1-14~D1-16（监控面板/SSH 远程，属独立文档）。

### 1.1 与 provider 策略的耦合（不可绕开）

`analysis/04` §三锁定 **MVP = OpenAI-only**，并保留 DeepSeek Tier-B 作为 `SDDP_LLM_MODEL=deepseek-chat` 的测试旁路（见 `backend/sddp/engine/agents.py:44` `_LLM_MODEL_OVERRIDE`）。因此密钥存储**至少**要容纳两个 provider 别名：`openai`（生产路径）与 `deepseek`（成本对照测试）。key 格式不同：

- OpenAI: `sk-proj-...` / `sk-...` (48 字符 base62)
- DeepSeek: `sk-` + 32 字符 hex

`prefilter.py` 的正则目录必须同时识别这两种（见 §五）。

---

## 二、密钥存储库锁定

### 2.1 候选与裁决

| 库 | 维护状态 (2026-07) | Win | macOS | Linux | Electron 集成 | 裁决 |
|----|---------------------|-----|-------|-------|---------------|------|
| **`keytar`** (`atom/node-keytar`) | **已归档** — Atom 组织随 Atom 编辑器 sunset (2022-12) 后停止维护；末版 v7.9.0 (2022)；README 已标注 "no longer maintained"，issue 全部冻结 | ✅ Cred Manager | ✅ Keychain | ✅ libsecret | N-API 原生模块；Electron 版本升级需重编 native 二进制（长期痛点） | ❌ **不采用**（归档 = 与 §03 §二"诚实声明"一致的不可依赖） |
| **`@napi-rs/keyring`** (`napi-rs/keyring`) | **活跃** — Rust `keyring-rs` crate 的 napi-rs 绑定；CI 定期跑；与 Electron ABI 兼容性靠 napi-rs 自动跨版本 | ✅ Cred Manager | ✅ Keychain | ✅ Secret Service (DBUS/libsecret) | 单一预编译 `.node` 二进制，跨 Electron 版本无需 rebuild | ✅ **采用为主路径** |
| **Electron `safeStorage`** (内置 API) | 内置于 Electron 主进程；语义稳定；无第三方依赖 | ✅ DPAPI | ✅ Keychain (data protection) | ✅ libsecret | `safeStorage.encryptString()` / `decryptString()`；产物是受 OS 主密钥保护的密文 blob | ✅ **采用为 fallback**（无 DBUS 的 headless Linux 开发机） |
| `keyring` (纯 JS) | 多个同名包，社区维护质量参差 | ⚠️ | ⚠️ | ⚠️ | 多数是对 PowerShell `cmdkey` / `security` 的子进程包装，脆弱 | ❌ 不采用 |

### 2.2 锁定版本

> 仿 `analysis/03` §二的诚实声明：在分析阶段直接断言一个具体 patch 号是不负责任的（npm 发布节奏 + Electron ABI 漂移 + 安全补丁频次），这里给**选型准则 + 候选版本 + 锁定脚本**。最终 patch 在 Dev-Phase 1 模块启动当天用 `npm view` 实查后写入 `package.json`。

**选型准则（按优先级）**：
1. **必须活跃**：近 90 天有 commit / release；归档包一律不收（keytar 已死，不破例）
2. **必须 prebuilt binary**：不接受需要 node-gyp 现场编译的包（与 Electron 的 ABI 漂移战不可妥协）
3. **必须三平台齐备**：Win/Mac/Linux 都有可用后端；缺一平台必须能在运行时检测并降级到 `safeStorage`
4. **必须 schema 稳定**：API 形如 `getPassword(service, account) / setPassword(service, account, password) / deletePassword(service, account)`，避免引入额外抽象层

**候选版本（实现时 `npm view` 实查锁定到精确 patch）**：

```jsonc
// package.json (Dev-Phase 1 第一天实查后填精确版本)
{
  "dependencies": {
    "@napi-rs/keyring": "^1.0.0"  // 候选; 锁定时改为 ==1.0.X
  }
}
```

```bash
# scripts/verify_keyring_version.sh (Dev-Phase 1 第 0 步)
TARGET="@napi-rs/keyring"
npm view "$TARGET" version                # 实查最新 stable
npm view "$TARGET" time --json            # 确认近 90 天有 release
npm install "$TARGET"
# 冒烟测试: 三平台都跑 (Win 跑 .node、Mac 跑 .node、Linux 跑 .node)
node -e "const k=require('$TARGET'); const e=k.getEntry('sddp-pet','smoke'); \
  e.setPassword('smoke-value'); \
  if (e.getPassword() !== 'smoke-value') process.exit(1); \
  e.deletePassword();"
# 期望: 退出码 0
```

**锁定产物**：
- `package.json`: `@napi-rs/keyring==1.0.X`（精确）
- `package-lock.json`: 含传递依赖完整 hash
- `KEYRING_VERSION_RATIONALE.md`: 记录准则 1-4 逐条对照 + 排除 keytar 的归档证据

### 2.3 为什么不直接用 Electron `safeStorage` 作主路径

`safeStorage` 在三平台都用 OS 主密钥加密一个 blob，blob 写到 `app.getPath('userData')` 下的文件。它也满足 D1-9 的字面要求（明文不落盘）。但：
1. **00-final §八原文**明确写 "Windows Credential Manager / macOS Keychain" — `safeStorage` 在 macOS 上确实走 Keychain，但在 Windows 上走的是 **DPAPI**（用户态文件加密），**不**写入 Credential Manager 凭据库。与设计文档措辞有偏差，需写文档变更说明。`@napi-rs/keyring` 则完全按原文走 Cred Manager。
2. **凭据库语义**：Cred Manager 提供"备份/导出/可见性"的产品级语义（用户可在控制面板 `rundll32 keymgr.dll,KRShowKeyMgr` 看到并删除 SDDP-Pet 的条目），更贴合"用户对自有密钥有控制权"的隐私承诺。
3. **跨用户场景**：DPAPI blob 绑定到 Windows 用户账户 + 机器；用户切换机器需重新粘贴。Cred Manager 条目也是用户态，但语义更清晰。

裁决：**`@napi-rs/keyring` 主路径**（三平台原生凭据库），**`safeStorage` 作 fallback**（headless Linux 开发机无 DBUS/secret-service 守护进程时自动降级；这是真实场景，因为按 00-final §六"目标平台: Windows 桌面，Linux 仅作远程服务器"，开发者可能用 SSH-only Linux 跳板机）。

---

## 三、密钥生命周期

### 3.1 写入（用户在 Electron 设置页粘贴 key）

```
[Electron Renderer: Settings.tsx]
  用户在 <input type="password"> 粘贴 "sk-proj-..."
  onClick "保存"
    ↓ IPC (ipcRenderer.invoke('secrets:set', {alias:'openai', value:'sk-proj-...'}))
[Electron Main: secrets/main.ts]
  1. 校验格式（正则：^sk-(proj-)?[A-Za-z0-9_\-]{20,}$；deepseek: ^sk-[a-f0-9]{32}$）
  2. backend = detectKeyringBackend()
       - 主路径: keyring.getEntry('SDDP-Pet', alias).setPassword(value)
       - fallback: encryptedBlob = safeStorage.encryptString(value)
                   fs.writeFile(userData/secrets/<alias>.enc, encryptedBlob)
  3. 在 ~/.sddp-pet/secrets.json 写一条**别名索引**（不是 key 本身！）:
       { "openai": { "backend": "keyring", "stored_at": "2026-07-21T..." },
         "deepseek": { "backend": "safestorage", ... } }
  4. 立刻从内存清除明文: value = '0'.repeat(value.length); del value
  ↓ IPC 返回 {ok:true}
[Renderer] 显示 "✓ 已保存到 Windows Credential Manager"
```

**关键不变量**：
- 明文 `sk-...` **绝不**写入 `~/.sddp-pet/` 下任何文件
- `secrets.json` 只存"哪个别名用了哪个 backend"，不存 key 本身
- 主进程在 IPC 处理结束后**立即覆写并释放**内存中的明文 buffer

### 3.2 读取（Python 引擎启动时）

```
[Electron Main: 启动 Python 子进程时]
  for alias in configured_providers():
      raw = readSecret(alias)   # keyring.getPassword 或 safeStorage.decryptString
      # 关键: 通过 stdin 注入环境变量, NOT command-line arg
      # (process list / `ps aux` 可见 argv; stdin 不可见)
  spawn('python', ['-m', 'sddp.cli.main', ...], {
      env: { ...process.env, OPENAI_API_KEY: raw.openai, SDDP_DEEPSEEK_KEY: raw.deepseek },
      stdio: ['pipe','pipe','pipe']
  })
  # 立即清零 raw buffer
[Python: backend/sddp/cli/main.py]
  current: use_mock = mock or not os.environ.get("OPENAI_API_KEY")  (line 86)
  DP1 改造: 环境变量仍然是真相源, 但来源从"用户 export"变成"Electron 主进程注入"
[Python: CrewAI Agent]
  CrewAI 内部从 OPENAI_API_KEY 环境变量读取 (见 backend/sddp/engine/agents.py:44 区域)
  → 传入 LLM 参数 (llm=openai_llm)
```

**为什么用 env var 注入而非 stdin / IPC 传 key**：
- CrewAI 与底层 langchain/openai SDK **强依赖** `OPENAI_API_KEY` 环境变量（已在 DP0 验证）。改协议 = 推翻 DP0 工作量。
- env var 在进程树内可见但**进程列表不可见**（`ps` 只显示 argv，不显示 env）。Linux/macOS 上 `/proc/<pid>/environ` 限同用户可读，Windows 上同用户态同样。
- 安全边界从"用户粘贴的 key 文件"上移到"OS 凭据库 + Electron 主进程 → 子进程 env"，明文不落盘。

### 3.3 轮换

用户在设置页粘贴新 key → 走与 §3.1 完全相同的路径（`setPassword` 覆盖旧值）。轮换策略：
- **不自动轮换**（用户自管）
- 引擎检测到 401/403 → 推送 `error` 消息（D1-5 已支持）+ UI 提示"key 可能已失效，请前往设置更新"
- 旧 key 在 Credential Manager 中被 `setPassword(newKey)` 原子覆盖，无残留

### 3.4 删除（卸载 / 用户主动清除）

```
[Electron Main: 卸载 hook 或 设置页"清除所有密钥"按钮]
  for alias in configured_providers():
      keyring.getEntry('SDDP-Pet', alias).deletePassword()
      -- 或 fallback: fs.unlink(userData/secrets/<alias>.enc)
  fs.unlink(~/.sddp-pet/secrets.json)
```

**已接受风险**：Windows MSI 卸载程序**不会**调用 Electron 的清理钩子（MSI 卸载是 out-of-process）。Credential Manager 中的条目会残留直到用户手动清理。**缓解**：在 EULA / 设置页显著位置告知用户"卸载后请运行 `sddp-pet --purge-secrets` 或在控制面板手动删除 SDDP-Pet 凭据"。登记到 §八。

### 3.5 时序图（一次完整流程）

```
用户      Electron Renderer    Electron Main        Keyring/safeStorage    Python Engine         OpenAI
 |  粘贴 key   |                    |                       |                     |                    |
 |------------>|  IPC secrets:set   |                       |                     |                    |
 |             |------------------->|  setPassword(alias,v) |                     |                    |
 |             |                    |---------------------->|                     |                    |
 |             |                    |  写 secrets.json 别名  |                     |                    |
 |             |                    |  (无明文)             |                     |                    |
 |             |<-------------------|  ok                   |                     |                    |
 |             | 显示 ✓             |                       |                     |                    |
 |  点"启动流程"|                    |                       |                     |                    |
 |------------>|  IPC flow:start    |                       |                     |                    |
 |             |------------------->|  getPassword(alias)   |                     |                    |
 |             |                    |---------------------->|                     |                    |
 |             |                    |<----------------------|  "sk-proj-..."      |                    |
 |             |                    |  spawn python + env 注入                     |                    |
 |             |                    |--------------------------------------------->|                    |
 |             |                    |  立即清零 env buffer                          | kickoff(inputs)   |
 |             |                    |                                              |------------------>|
 |             |                    |                                              |<------------------|
 |             |                    |                                              |  StructuredOutput |
 |             |                    |                                              |  清零 OPENAI_API_KEY buffer
```

---

## 四、D1-9 验证方法

DoD 原文（`dod.md:65`）：
> `grep -r "sk-" ~/.sddp-pet/` 无命中；密钥读取走 Credential Manager API

### 4.1 让 grep 测试通过的工程要求

1. **`~/.sddp-pet/` 下绝不存明文 key**。允许的内容：
   - `secrets.json`（**别名索引**，仅含 `{"openai": {"backend":"keyring"}}` 形式）
   - `config.json`（其他配置）
   - `flows/<flow_id>/` 流程持久化（@persist 数据；D1-11 预过滤后**理论上不含**真实 key，但需配合 §五）
   - `metrics.json`、`cost_report.json`（DP0 已有）
2. **示例文件去敏感化**：DP0 的 `backend/scripts/deepseek-env.sh.example:8` 现含 `export DEEPSEEK_API_KEY="sk-replace-me"`。这是**示例占位符**，不是真实 key，但 `grep -r "sk-" ~/.sddp-pet/` 不会扫到 `backend/`（路径不同），因此**不破坏** D1-9。但 `backend/README.md` 与 docs 中如果出现 `sk-` 前缀的真实示例需全部改成 `<your-key>` 占位。
3. **日志脱敏**：所有 logger 输出经过 `prefilter.redact()`（见 §五）；CostMeter / SafeAgent 不得在异常 message 中带 key（DP0 `wrapper.py:312` `"message": f"{type(exc).__name__}: {exc}"[:500]` 在异常文本可能含 key 时必须先 redact）。

### 4.2 验证脚本（D1-9 验收命令）

```bash
# scripts/verify_d1_9_secret_storage.sh
set -e

# 前置: 用户已在设置页粘贴过一个真实 OpenAI key
# 前置: ~/.sddp-pet/secrets.json 存在

# 1. 磁盘零明文 key 测试
if grep -rE "sk-(proj-)?[A-Za-z0-9_\-]{20,}" ~/.sddp-pet/; then
    echo "FAIL: 明文 key 出现在 ~/.sddp-pet/"
    exit 1
fi

# 2. DeepSeek 格式也测一遍 (32 hex)
if grep -rE "sk-[a-f0-9]{32}" ~/.sddp-pet/; then
    echo "FAIL: DeepSeek 明文 key 出现在 ~/.sddp-pet/"
    exit 1
fi

# 3. Credential Manager 实际有条目 (Windows)
#    PowerShell 列出 SDDP-Pet 命名空间下的凭据
if [[ "$OS" == "Windows_NT" ]] || [[ "$(uname -s)" == MINGW* ]]; then
    powershell.exe -NoProfile -Command "
        \$mgr = New-Object -ComObject 'Microsoft.Windows.CredentialManager'  # 注: 实际用 cmdkey 或 API
        cmdkey /list:WindowsLive:target=SDDP-Pet* 2>\$null | Select-String 'SDDP-Pet'
    " | grep -q 'SDDP-Pet' || { echo 'FAIL: Credential Manager 无 SDDP-Pet 条目'; exit 1; }
fi

# 4. 引擎能读到 key (端到端)
SDDP_LLM_MODEL=mock python -m sddp.cli.main --self-check-secrets && \
    echo "OK: 引擎通过 OS API 读到 key" || { echo "FAIL: 引擎读不到 key"; exit 1; }

echo "D1-9 PASS"
```

`--self-check-secrets` 是 DP1 新增 CLI 子命令：从 env var（Electron 注入的）读 key 并 ping 一次 `/v1/models`，成功返回 0。

### 4.3 反例（哪些写法会让 D1-9 失败）

| 错误写法 | 为何失败 |
|---------|---------|
| `fs.writeFile('~/.sddp-pet/openai_key.txt', apiKey)` | 明文落盘，grep 命中 |
| `config.json: {"openai_key": "sk-proj-..."}` | 同上 |
| `logger.info(f"Using key {api_key[:8]}...")` | 日志含 key 前缀；若日志写到 `~/.sddp-pet/logs/` 则 grep 命中 |
| Electron 主进程 `process.argv.push('--api-key='+key)` | argv 出现在 `ps`/进程列表（但 D1-9 grep 不扫进程列表，仅扫 `~/.sddp-pet/`；不过仍是 D1-11 之外的隐性风险） |

---

## 五、代码预过滤设计 (Python, `sddp/security/prefilter.py`)

### 5.1 目标与边界

DoD 原文（`dod.md:67`）：
> 输入代码 → 脱敏摘要（密钥/密文/PII 替换为占位符）→ 仅发送脱敏摘要到远程；`tests/security/test_prefilter.py` 固定输入产生固定脱敏输出

**做什么**：在代码片段进入 LLM prompt 之前，用正则把密钥/PII/凭据替换为可逆占位符（如 `<<REDACTED_OPENAI_KEY_1>>`），LLM 返回的内容若有占位符则还原为原值。

**不做什么**（明确已接受风险，登记到 §八）：
- **不是密码学脱敏**：正则匹配有漏报（变量名拼接的 key、base64 编码、被切片的 key）
- **不做语义分析**：不识别"这段代码逻辑虽无 key 但暴露了内部 API 端点"这类上下文泄露
- **不替换代码逻辑**：函数名、变量名、控制流保留（避免 LLM 失去推理能力）

### 5.2 模块骨架（提案路径 `backend/sddp/security/prefilter.py`）

```python
# backend/sddp/security/prefilter.py
"""Code pre-filter: redact secrets/PII before sending to remote LLM (D1-11).

Per analysis/09 §五: regex-based, NOT cryptographic desensitization.
Integration point: wrap the inputs dict passed to SafeAgent.kickoff() at the
architect / executor agent boundary (see backend/sddp/engine/agents.py).
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

# ---- Regex catalog (sources: gitleaks 8.x default ruleset + truffleHog patterns) ----
# Order matters: more specific patterns first to avoid partial overlaps.
SECRET_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    # OpenAI (Tier-S, analysis/04 §三)
    ("OPENAI_PROJECT_KEY", re.compile(r"sk-proj-[A-Za-z0-9_\-]{40,}"), "<<REDACTED_OPENAI_PROJ_{n}>>"),
    ("OPENAI_LEGACY_KEY",  re.compile(r"sk-[A-Za-z0-9]{48}"),          "<<REDACTED_OPENAI_LEGACY_{n}>>"),
    # DeepSeek (Tier-B, analysis/04; 32-char hex)
    ("DEEPSEEK_KEY",       re.compile(r"sk-[a-f0-9]{32}"),             "<<REDACTED_DEEPSEEK_{n}>>"),
    # Anthropic
    ("ANTHROPIC_KEY",      re.compile(r"sk-ant-[A-Za-z0-9_\-]{93}"),   "<<REDACTED_ANTHROPIC_{n}>>"),
    # Cloud providers
    ("AWS_ACCESS_KEY_ID",  re.compile(r"AKIA[0-9A-Z]{16}"),            "<<REDACTED_AWS_AKID_{n}>>"),
    ("AWS_SECRET",         re.compile(r"(?i)aws_secret(?:_access_key)?\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}"), "<<REDACTED_AWS_SECRET_{n}>>"),
    ("GITHUB_PAT",         re.compile(r"github_pat_[A-Za-z0-9_]{82}"), "<<REDACTED_GH_PAT_{n}>>"),
    ("GITHUB_TOKEN",       re.compile(r"gh[pousr]_[A-Za-z0-9]{36}"),   "<<REDACTED_GH_TOKEN_{n}>>"),
    ("GOOGLE_API_KEY",     re.compile(r"AIza[0-9A-Za-z_\-]{35}"),      "<<REDACTED_GOOGLE_{n}>>"),
    ("STRIPE_KEY",         re.compile(r"(?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{24}"), "<<REDACTED_STRIPE_{n}>>"),
    ("SLACK_TOKEN",        re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), "<<REDACTED_SLACK_{n}>>"),
    # Private keys (PEM block) — non-greedy across the block
    ("PRIVATE_KEY_BLOCK",  re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |)PRIVATE KEY-----[\s\S]+?-----END (?:RSA |EC |DSA |OPENSSH |)PRIVATE KEY-----"), "<<REDACTED_PEM_{n}>>"),
    # JWT
    ("JWT",                re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "<<REDACTED_JWT_{n}>>"),
    # Generic (LOW confidence; must be last to avoid clobbering specific patterns)
    ("GENERIC_API_KEY",    re.compile(r"(?i)(?:api[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}"), "<<REDACTED_API_KEY_{n}>>"),
    ("GENERIC_SECRET",     re.compile(r"(?i)(?:secret|passwd|password|token)\s*[:=]\s*['\"]?[^\s'\"\)]{8,}"), "<<REDACTED_SECRET_{n}>>"),
]

# PII (lower confidence; applied after secrets to avoid double-redaction)
PII_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("EMAIL",   re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "<<REDACTED_EMAIL_{n}>>"),
    # Phone numbers intentionally omitted in DP1: false-positive rate too high
    # on code containing numeric constants. Revisit in Dev-Phase 4.
]


@dataclass
class RedactionResult:
    redacted_text: str
    restoration_map: dict[str, str] = field(default_factory=dict)  # placeholder -> original

    def restore(self, text: str) -> str:
        """Restore placeholders in LLM output back to original values."""
        out = text
        for placeholder, original in self.restoration_map.items():
            out = out.replace(placeholder, original)
        return out


def redact(text: str, *, include_pii: bool = True) -> RedactionResult:
    """Redact secrets/PII in `text`. Returns redacted text + restoration map.

    Determinism (D1-11 requirement: "fixed input → fixed output"):
    - Patterns applied in declared order
    - Placeholder counter {n} monotonically increases per pattern type within one call
    - Same input always yields same {placeholder -> original} map
    """
    restoration: dict[str, str] = {}
    out = text

    def _apply(catalog: list[tuple[str, re.Pattern[str], str]]) -> None:
        nonlocal out
        for _name, pat, tmpl in catalog:
            counter = 0
            def _sub(m: re.Match[str], _pat=pat, _tmpl=tmpl) -> str:
                nonlocal counter
                counter += 1
                placeholder = _tmpl.format(n=counter)
                restoration[placeholder] = m.group(0)
                return placeholder
            out = pat.sub(_sub, out)

    _apply(SECRET_PATTERNS)
    if include_pii:
        _apply(PII_PATTERNS)
    return RedactionResult(redacted_text=out, restoration_map=restoration)
```

### 5.3 集成点：包裹 SafeAgent 的 inputs

DP0 现状（`backend/sddp/engine/agents.py`）：
```python
safe = SafeAgent(name="architect", kickoff_fn=agent.kickoff)
result = safe.kickoff(inputs)   # inputs 含 code_snippet 字段, 直接进 prompt
```

DP1 改造（提案）：在 `agents.py` 工厂层注入 prefilter，对所有"接触用户代码"的角色（架构师 / 实施师 / 代码资产管理员）启用；对纯流程控制角色（需求官 / 调度官）可选关闭以省 token。

```python
# backend/sddp/engine/agents.py (DP1 改造, 约 line 200+)
from ..security.prefilter import redact

class CodeAwareSafeAgent(SafeAgent):
    """SafeAgent variant that redacts code in inputs before kickoff, restores
    placeholders in output. Used by architect / executor / code_asset_manager."""

    CODE_INPUT_FIELDS = ("code_snippet", "file_content", "diff", "context_code")

    def kickoff(self, inputs: dict | None = None) -> Any:
        if inputs:
            redaction_map: dict[str, RedactionResult] = {}
            new_inputs = {**inputs}
            for fld in self.CODE_INPUT_FIELDS:
                if fld in new_inputs and isinstance(new_inputs[fld], str):
                    r = redact(new_inputs[fld])
                    new_inputs[fld] = r.redacted_text
                    redaction_map[fld] = r
            result = super().kickoff(new_inputs)
            # 还原输出中的占位符 (LLM 常在解释中引用代码片段)
            if isinstance(result, str):
                for r in redaction_map.values():
                    result = r.restore(result)
            elif hasattr(result, "model_dump"):
                dumped = result.model_dump()
                for r in redaction_map.values():
                    _restore_in_place(dumped, r)
                # 重建为同类型 (pydantic)
                result = type(result).model_validate(dumped)
            return result
        return super().kickoff(inputs)
```

**关键约束**：
- 占位符**必须**显眼（`<<REDACTED_*>>`），便于人工审计与日志检查
- 还原**仅发生在引擎进程内**，**不**回写到磁盘 / 不进日志 / 不进遥测
- 测试 fixture（`tests/security/test_prefilter.py`）必须包含至少 14 个固定用例（每个 pattern 一条），断言"固定输入 → 固定输出"

### 5.4 与 D1-9 grep 测试的耦合

`prefilter.redact()` 也用于**日志脱敏**：SafeAgent 失败时（`wrapper.py:312`）的 `message` 字段必须先 redact 再写 state.errors，否则异常文本里的 key 会通过 @persist 落到 `~/.sddp-pet/flows/<id>/state.json`，**破坏 D1-9**。

---

## 六、隐私同意 (D1-10) + AI 标注 (D1-12)

### 6.1 隐私同意流程

**触发时机**：
1. 首次启动应用（`localStorage.getItem('sddp:privacy_consent') === null`）
2. 用户在设置页切换 provider（OpenAI ↔ DeepSeek，因数据接收方不同）
3. 升级到含新数据流向的版本（版本号比对，DP1 不实现，留 TODO）

**UI 流程**：

```
[App.tsx onMount]
  if (!localStorage['sddp:privacy_consent'] ||
      localStorage['sddp:privacy_consent_provider'] !== currentProvider) {
      render <PrivacyConsentModal provider={currentProvider} />
  }

[PrivacyConsentModal]
  ┌──────────────────────────────────────────────────────┐
  │  ⚠️  数据将发送到远程 LLM                              │
  │                                                       │
  │  本应用使用 {provider == 'openai' ? 'OpenAI' :        │
  │     'DeepSeek'} 作为 AI 后端。你提交的代码、需求描述、  │
  │  以及桌宠对话内容将被加密传输到该 provider 的服务器。  │
  │                                                       │
  │  • 代码已本地预过滤（密钥/PII 替换为占位符）            │
  │  • 遥测已硬性禁用 (OTEL_SDK_DISABLED=true)            │
  │  • 你可以随时在设置中清除所有密钥与历史                │
  │                                                       │
  │      [ 拒绝 ]              [ 同意并继续 ]              │
  └──────────────────────────────────────────────────────┘

  拒绝 → localStorage['sddp:privacy_consent'] = 'declined'
         主流程 start_flow 按钮置灰, 显示 banner "需先同意隐私协议"
         不退出应用 (用户仍可浏览设置/查看历史)
  同意 → localStorage['sddp:privacy_consent'] = 'accepted'
         localStorage['sddp:privacy_consent_provider'] = currentProvider
         localStorage['sddp:privacy_consent_ts'] = new Date().toISOString()
         关闭 modal, start_flow 按钮可点
```

**关键约束**：
- 同意状态存 `localStorage`（Renderer 进程持久化），**不**进 Python 引擎
- `start_flow` RPC 在 Electron Main 层拦截：渲染层虽被绕过（开发者工具改 localStorage），但 IPC handler 二次校验 consent 状态
- 拒绝**不退出应用**：用户可看历史/改设置，仅"启动新流程"被禁

**验证命令**（D1-10）：
```bash
# E2E (Playwright on Electron)
1. 删除 %APPDATA%/sddp-pet/Local Storage/* (清 consent)
2. 启动 app
3. assert: PrivacyConsentModal 可见
4. click("拒绝")
5. assert: start_flow 按钮 disabled
6. 重启 app
7. assert: Modal 再次出现 (consent 未持久化为 accepted)
8. click("同意并继续")
9. assert: start_flow 按钮 enabled
10. 重启 app
11. assert: Modal 不再出现
```

### 6.2 AI 标注

**要求**（`dod.md:68`）：桌宠气泡旁标注"AI 驱动"，UI 检查标注可见。

**方案选择**：

| 方案 | 实现 | 优点 | 缺点 | 裁决 |
|------|------|------|------|------|
| **A. CSS overlay** | 在窗口 1 的 canvas 上方叠一个透明 `<div>`，position: fixed 角落，文本"AI 驱动"+ 图标 | 实现简单；不污染 PixiJS 渲染管线；字体渲染清晰（DOM） | 与穿透点击冲突（DOM 节点会拦截鼠标） | ❌ 与 D1-3 穿透点击冲突 |
| **B. PixiJS Text** | 在 PixiJS stage 上加一个 `PIXI.Text("AI 驆动", {...})` 固定到角落 | 与桌宠同层，穿透点击统一处理；窗口缩放/移动时跟随 | 字体渲染不如 DOM 锐利；需管理 z-order | ✅ **采用** |
| **C. 独立小窗口** | 单开第三个透明窗口专门放标注 | 隔离干净 | 多一个窗口 = 多一份渲染开销；窗口叠放顺序管理复杂 | ❌ 过度工程 |

**采用方案 B**：在窗口 1 的 PixiJS stage 角落渲染 `PIXI.Text("AI 驱动", {fontSize:12, fill:'#888'})`，常驻显示，不受气泡显隐影响。z-order 设为最顶层，但 `interactive=false`（不拦截 pointer 事件，避免破坏穿透点击）。

**验证命令**（D1-12）：
```bash
# E2E: 截图 + 像素比对 / 或读取 PixiJS stage children
1. 启动 app (含桌宠)
2. 通过 DevTools (窗口1) 执行:
   const app = window.__PIXI_APP__;
   const labels = app.stage.children.filter(c => c instanceof PIXI.Text);
   assert: labels.some(t => t.text === "AI 驱动");
3. 或: 截图, OCR 比对包含 "AI 驱动"
```

---

## 七、OTEL 禁用 (D1-13)

### 7.1 现状

DP0 `backend/requirements.lock.txt:86-92` 显示 OpenTelemetry SDK 与多个 exporter 已作为**传递依赖**进入项目（来自 CrewAI/langchain 链路）：

```
opentelemetry-api==1.42.1
opentelemetry-exporter-otlp-proto-common==1.42.1
opentelemetry-exporter-otlp-proto-grpc==1.42.1
opentelemetry-exporter-otlp-proto-http==1.42.1
opentelemetry-proto==1.42.1
opentelemetry-sdk==1.42.1
opentelemetry-semantic-conventions==0.63b1
```

若 SDK 默认初始化 + exporter 默认 endpoint（`http://localhost:4317` 或环境配的 OTLP collector），**启动即可能尝试上报**，即便没有 collector 在听，也是不必要的外发。

### 7.2 禁用机制

OpenTelemetry 规范定义了通用 SDK 环境变量 `OTEL_SDK_DISABLED`（参考 OpenTelemetry Specifications → SDK Environment Variables → General SDK Configuration；Python SDK 与 Node SDK 均合规）。设为 `true` 时，SDK 返回 no-op tracer/meter/logger provider，**完全短路**所有 export 路径——比单独把 exporter 设为 `none` 更彻底（后者仍会初始化 provider 与 processing pipeline）。

**实现（硬编码，不可被用户配置覆盖）**：

```python
# backend/sddp/__init__.py (在所有其他 import 之前)
import os
# D1-13: 硬性禁用 OTEL, 早于任何 opentelemetry-* 包被 import
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
# setdefault 而非赋值: 允许开发者临时 export OTEL_SDK_DISABLED=false 排查问题,
# 但默认(用户未设置时)是禁用. 注: 若 DoD 要求"绝对硬编码"可改为直接赋值.

# 然后才 import 其他模块
from . import engine  # noqa: E402
```

```typescript
// electron/main.ts (Electron 主进程, spawn Python 之前)
process.env.OTEL_SDK_DISABLED = 'true';  // 覆盖, 不用 setdefault
// 同时设给 Electron 自身 (electron 也可能被 opentelemetry-js instrument)
process.env.OTEL_SDK_DISABLED = 'true';
```

**裁决**：用 `setdefault`（Python 侧）允许开发者排查时临时打开；Electron 侧硬赋值（产品形态下用户不会改 env，开发者可在 dev 模式覆盖）。若 DoD 验收要求"无条件硬编码"，Python 侧也改为硬赋值。**当前裁决**：Python 用 `setdefault`，验收脚本（§7.3）以"用户态启动"为准——用户态启动下 env 未设 `OTEL_SDK_DISABLED`，setdefault 生效为 true。

### 7.3 验证（网络嗅探测试）

DoD 原文（`dod.md:69`）：进程启动后无 OTEL 上报网络请求。

```bash
# scripts/verify_d1_13_otel_disabled.sh
# 思路: 启动 app + 引擎, 抓 60s 网络流量, 断言无任何到 OTLP 默认端口的连接

set -e

# 1. 启动 tcpdump 抓包 (需 root; 或用 mock collector)
sudo tcpdump -i any -w /tmp/otel-sniff.pcap 'port 4317 or port 4318' &
TCPDUMP_PID=$!
sleep 2

# 2. 启动 app (用户态, 模拟真实用户)
sddp-pet &
APP_PID=$!

# 3. 触发一次完整流程 (会调用多个 agent)
sddp run "add a hot-reload config feature" --mock   # mock 模式跑流程, 不需真实 key

# 4. 等 60s (默认 OTLP export 间隔通常 5-15s, 60s 足够覆盖多次 batch)
sleep 60

# 5. 停止
kill $APP_PID $TCPDUMP_PID

# 6. 断言: pcap 文件大小为 0 (无任何包)
PACKETS=$(tcpdump -r /tmp/otel-sniff.pcap 2>/dev/null | wc -l)
if [ "$PACKETS" -ne 0 ]; then
    echo "FAIL: 检测到 $PACKETS 个 OTLP 包"
    tcpdump -r /tmp/otel-sniff.pcap -n
    exit 1
fi

# 7. 替代/补充: 跑一个 mock collector, 看是否收到任何数据
docker run -d --name mock-otel-collector -p 4317:4317 \
    otel/opentelemetry-collector:latest
# (省略配置; collector 默认监听 4317 grpc / 4318 http)
# 启动 app, 跑流程, 检查 collector 日志: 应无任何 exported span/metric/log
docker logs mock-otel-collector | grep -i "export" && exit 1 || echo "D1-13 PASS"
```

**注意**：tcpdump 需 root，CI 环境不一定可用；mock-collector 方案更 CI 友好。验收时二选一。

---

## 八、已接受风险

| 风险 | 严重度 | 说明 / 缓解 |
|------|--------|-------------|
| DP1 仅 Windows Credential Manager 走原生凭据库语义；macOS/Linux 走 keyring 默认实现可能弹 OS 权限对话框（首次写入触发） | 低 | 文档告知 + 设置页"如弹权限框请点同意"；不影响功能 |
| Headless Linux（无 DBUS / 无 secret-service 守护）下 `@napi-rs/keyring` 不可用，必须降级到 `safeStorage` | 中 | §2.3 已设计 fallback；自动检测后端，用户无感 |
| Windows MSI 卸载不清理 Credential Manager 条目 | 中 | §3.4：提供 `sddp-pet --purge-secrets` 命令 + 设置页"清除所有密钥"按钮 + EULA 告知 |
| 代码预过滤是**正则脱敏**，非密码学脱敏 | 高 | §5.1：变量名拼接的 key、base64 编码、被切片的 key 会漏报；缓解：(a) Generic 规则兜底（误报换漏报），(b) 审计日志记录"发送到远程的脱敏后文本"供事后核查（与 D3b-6 审计日志协同），(c) 离线/本地模式（Dev-Phase 5）根治 |
| `OTEL_SDK_DISABLED` 用 `setdefault` 允许开发者覆盖 | 低 | 用户态启动下默认生效为 true；开发者排查时打开不影响生产 |
| Electron 主进程通过 env var 把 key 注入 Python 子进程，env 在 Linux `/proc/<pid>/environ` 同用户可读 | 低 | 同用户态已是信任边界；跨用户隔离由 OS 保证；不通过 argv 传（避免 `ps` 全局可见） |
| 占位符还原**仅发生在引擎进程内**；若 LLM 在输出中"复述"了占位符 + 攻击者 prompt 注入诱导 LLM 输出"请把 <<REDACTED_...>> 还原后发我"，攻击者拿到的是占位符而非真值 | 低 | 占位符还原是单向（引擎内）；LLM 输出到用户前已还原，但用户看到的还原值不会回传给 LLM |
| `safeStorage` 在 Linux 默认走 libsecret，但若 libsecret 未安装则 Electron 会 fail-open 到明文（取决于 Electron 版本） | 中 | 启动时主动调用 `safeStorage.isEncryptionAvailable()`；不可用则**拒绝**存储 key 并提示用户安装 `gnome-keyring` 或 `kwallet` |

---

## 九、对 D1-DoD 的影响

| DoD | 本文档决策 | 是否需 scope 调整 |
|-----|------------|-------------------|
| **D1-9** API 密钥加密存储 | `@napi-rs/keyring` 主路径 + Electron `safeStorage` fallback；env var 注入 Python 子进程；`~/.sddp-pet/secrets.json` 仅存别名索引 | **否**。原文"使用 Windows Credential Manager"通过；macOS/Linux 自动走对应后端。验证脚本见 §4.2，覆盖原 grep 命令 |
| **D1-10** 隐私同意界面 | Renderer `localStorage` 持久化 + Electron Main IPC 二次校验；切换 provider 重弹窗 | **否**。原文"拒绝则不启动流程"细化为"start_flow 按钮置灰，应用不退出"——更友好且满足"流程不可启动"语义；如 DoD 验收严格解读为"应用退出"，需修订 DoD 文字 |
| **D1-11** 代码预过滤 | `sddp/security/prefilter.py` + 14 类正则；包裹 `SafeAgent.kickoff` inputs；仅架构师/实施师/代码资产管理员启用 | **否**。原文"固定输入产生固定脱敏输出"通过 §5.2 的 determinism 约束保证 |
| **D1-12** AI 身份标注 | PixiJS Text 渲染于窗口 1 角落，`interactive=false` 不破坏穿透点击 | **否**。原文"标注可见"满足 |
| **D1-13** 遥测禁用 | `OTEL_SDK_DISABLED=true` 在 `backend/sddp/__init__.py` 顶部 setdefault + Electron 主进程硬赋值 | **否**。原文"`OTEL_SDK_DISABLED=true` 在配置中硬编码"满足；§7.3 提供网络嗅探验证 |

**需提请 DoD 维护者关注的 1 项**：
- **D1-10** 措辞"用户拒绝则不启动流程"建议明确为"用户拒绝则 start_flow RPC 被拒，应用继续运行供查看历史/设置"。否则按字面"不启动流程"可被解读为"应用退出"，与本设计的友好降级语义冲突。

**未受本文档影响的 D1 项**：D1-1 ~ D1-8（前端窗口/WebSocket，见 10 号文档）、D1-14/D1-15（监控指标，见可观测性文档）、D1-16（SSH 远程模式，见远程部署文档）。

---

## 十、参考与证据

- `analysis/00-sddp-pet-final.md` §八合规性表 (lines 243-257)、§十三缺失考虑 (lines 389-408)
- `analysis/03-crewai-version-strategy.md` §二诚实声明风格、§五SafeAgent 硬性前提
- `analysis/04-llm-provider-strategy.md` §三 OpenAI-only 锁定、§四 provider 抽象层
- `openspec/specs/development-roadmap/dod.md` Dev-Phase 1 (lines 53-72)
- DP0 代码路径: `backend/sddp/cli/main.py:86` (env var 真相源)、`backend/sddp/engine/agents.py:44` (provider override)、`backend/sddp/safe_agent/wrapper.py:312` (异常 message 需 redact)、`backend/scripts/deepseek-env.sh:30` (key 注入现状)、`backend/requirements.lock.txt:86-92` (OTEL 传递依赖)
- OpenTelemetry 通用 SDK 配置规范: `OTEL_SDK_DISABLED` (General SDK Configuration) — Python SDK / Node SDK 均合规
- 密钥正则目录参考: gitleaks 8.x 默认规则集、truffleHog detector 列表
- **证据完整性声明**：本文档成文时 WebFetch 对 `github.com/atom/node-keytar` 与 `github.com/napi-rs/keyring` 在本环境多次超时未取到 README；keytar 归档状态与 `@napi-rs/keyring` 活跃状态基于既有知识。Dev-Phase 1 第 0 步**必须**用 `npm view` 实查最新维护状态与版本号，写入 `KEYRING_VERSION_RATIONALE.md` 后方可锁定（与 `analysis/03` §二同等约束）。
