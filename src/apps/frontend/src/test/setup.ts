import "@testing-library/jest-dom/vitest";

if (
  typeof globalThis.localStorage !== "object" ||
  globalThis.localStorage === null ||
  typeof globalThis.localStorage.clear !== "function"
) {
  const store = new Map<string, string>();
  const storageShim = {
    getItem(key: string): string | null {
      return store.has(key) ? store.get(key)! : null;
    },
    setItem(key: string, value: string): void {
      store.set(String(key), String(value));
    },
    removeItem(key: string): void {
      store.delete(String(key));
    },
    clear(): void {
      store.clear();
    },
    key(index: number): string | null {
      return Array.from(store.keys())[index] ?? null;
    },
    get length(): number {
      return store.size;
    },
  };
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storageShim,
  });
}
