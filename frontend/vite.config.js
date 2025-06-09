import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig(({ mode }) => {
    // Load env file based on `mode` in the current working directory.
    const env = loadEnv(mode, process.cwd());
    
    return {
        plugins: [vue()],
        server: {
            proxy: {
                '/api': {
                    target: `http://${env.HOST || 'localhost'}:${env.BACKEND_PORT || 3000}`,
                    changeOrigin: true,
                    rewrite: (path) => path.replace(/^\/api/, '')
                }
            }
        }
    };
});
