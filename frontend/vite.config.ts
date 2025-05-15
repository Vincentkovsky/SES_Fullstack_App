import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:3000', // Backend API URL
        changeOrigin: true,             // Handle CORS by simulating the same origin
        rewrite: (path) => path.replace(/^\/api/, '') // Remove `/api` prefix if necessary
      }
    }
  },
  build: {
    // 禁用类型检查
    typescript: {
      transpileOnly: true
    },
    assetsDir: 'assets',
    rollupOptions: {
      output: {
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]'
      }
    }
  },
  publicDir: 'public'
});