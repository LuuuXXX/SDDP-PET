import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement postMessage fully; we keep window.postMessage but ensure
// it doesn't crash. Real DOM message events work fine.
if (typeof window !== "undefined" && typeof window.postMessage !== "function") {
  window.postMessage = (() => {}) as unknown as Window["postMessage"];
}

// jsdom doesn't have matchMedia; React 19 hooks sometimes need it.
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    value: () => ({
      matches: false,
      media: "",
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}
