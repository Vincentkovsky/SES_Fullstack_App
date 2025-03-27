/// <reference types="vite/client" />

// 扩展 ImportMeta 接口以包含 env
interface ImportMeta {
  readonly env: {
    readonly VITE_OPENWEATHERMAP_API_KEY: string;
    readonly VITE_MAPBOX_ACCESS_TOKEN: string;
    readonly [key: string]: string;
  };
}
