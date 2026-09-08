<script setup lang="ts">
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  LayoutDashboard,
  Server,
  Network,
  Database,
  ShieldAlert,
  Layers,
  ShieldCheck,
  LogOut,
  KeyRound
} from 'lucide-vue-next'

const authStore = useAuthStore()
const route = useRoute()

const menuItems = computed(() => {
  const items = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Ativos', path: '/assets', icon: Server },
    { name: 'Infraestrutura', path: '/infrastructure', icon: Network },
    { name: 'Dados Mestres', path: '/reference-data', icon: Database },
    { name: 'Integrações', path: '/integrations', icon: Layers },
    { name: 'Auditoria', path: '/audit', icon: ShieldAlert },
  ]
  if (authStore.isAdmin) {
    items.push({ name: 'Administração', path: '/admin', icon: ShieldCheck })
  }
  return items
})

const pageTitle = computed(() => {
  const routeTitles: Record<string, string> = {
    dashboard: 'Dashboard',
    assets: 'Inventário de Ativos',
    infrastructure: 'Infraestrutura & Mapa de TI',
    'reference-data': 'Tabelas Auxiliares',
    audit: 'Trilha de Auditoria',
    integrations: 'Integrações & Automações',
    admin: 'Administração'
  }
  return routeTitles[route.name as string] || 'SGTI - CMDB'
})
</script>

<template>
  <div class="flex h-screen bg-slate-900 text-slate-100">
    <!-- Sidebar -->
    <aside class="w-64 border-r border-slate-800 bg-slate-950 flex flex-col">
      <div class="h-16 flex items-center px-6 border-b border-slate-800">
        <span class="font-bold text-lg tracking-wider text-emerald-400">SGTI</span>
        <span class="ml-2 text-[10px] text-slate-500 font-mono uppercase tracking-widest">CMDB</span>
      </div>

      <nav class="flex-1 px-4 py-4 space-y-1">
        <RouterLink
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors hover:bg-slate-800 text-slate-400 hover:text-slate-100"
          active-class="!bg-emerald-600/10 !text-emerald-400 border border-emerald-500/20"
        >
          <component :is="item.icon" class="w-4 h-4" />
          {{ item.name }}
        </RouterLink>
      </nav>

      <div class="p-4 border-t border-slate-800">
        <div class="px-3 pb-3">
          <div class="flex items-center gap-2 text-xs text-slate-300">
            <KeyRound class="w-3.5 h-3.5 text-slate-500" />
            <span class="truncate font-mono">{{ authStore.userName }}</span>
          </div>
          <div class="flex gap-1 mt-1.5 flex-wrap">
            <span
              v-for="role in authStore.roles"
              :key="role"
              class="text-[9px] font-medium px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 uppercase tracking-wider"
            >
              {{ role }}
            </span>
          </div>
        </div>

        <button
          @click="authStore.logout"
          class="w-full flex items-center gap-3 px-3 py-2 text-sm text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
        >
          <LogOut class="w-4 h-4" />
          Desconectar
        </button>
      </div>
    </aside>

    <!-- Main Content -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <header class="h-16 border-b border-slate-800 bg-slate-950/50 flex items-center justify-between px-8">
        <h1 class="text-sm font-semibold uppercase tracking-wider text-slate-400">
          {{ pageTitle }}
        </h1>
        <div class="flex items-center gap-3">
          <span class="text-xs bg-slate-800 px-2.5 py-1 rounded text-slate-300 font-mono">
            ...::: SGTI - CMDB :::...
          </span>
        </div>
      </header>

      <main class="flex-1 overflow-y-auto p-8 bg-slate-900/50">
        <RouterView />
      </main>
    </div>
  </div>
</template>