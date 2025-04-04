import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy API requests starting with /mcp to the backend server
      '/mcp': {
        target: 'http://localhost:8000', // Default backend server address
        changeOrigin: true, // Needed for virtual hosted sites
        // rewrite: (path) => path.replace(/^\/api/, ''), // Optional: remove base path
      },
      // You might need to proxy other paths if your backend serves more
    },
  },
})
