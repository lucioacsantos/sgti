// Objetivo: Ponto de entrada Vue: cria app, instala Pinia e router e monta no DOM.
// Author: Lucio A C Santos — GitHub: https://github.com/lucioacsantos

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')