import { createApp } from 'vue'
import ui from '@nuxt/ui/vue-plugin'
import App from './App.vue'
import '@fontsource/figtree/400.css'
import '@fontsource/figtree/500.css'
import '@fontsource/figtree/600.css'
import '@fontsource/fredoka/500.css'
import '@fontsource/fredoka/600.css'
import './style.css'

createApp(App).use(ui).mount('#app')
