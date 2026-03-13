/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_QUEEN_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
