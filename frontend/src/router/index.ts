import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/auth/LoginView.vue')
    },
    {
      path: '/',
      component: () => import('@/layouts/AdminLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: '/dashboard'
        },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue')
        },
        /*{
          path: 'assets',
          name: 'assets',
          component: () => import('@/views/assets/AssetsView.vue')
        },
        {
          path: 'infrastructure',
          name: 'infrastructure',
          component: () => import('@/views/infrastructure/InfraView.vue')
        },*/
        {
          path: 'reference-data',
          name: 'reference-data',
          component: () => import('@/views/reference/ReferenceDataView.vue')
        }/*,
        {
          path: 'audit',
          name: 'audit',
          component: () => import('@/views/audit/AuditView.vue')
        },
        {
          path: 'integrations',
          name: 'integrations',
          component: () => import('@/views/integrations/IntegrationsView.vue')
        } */
      ]
    }
  ]
})

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'login' })
  } else if (to.name === 'login' && authStore.isAuthenticated) {
    next({ name: 'dashboard' })
  } else {
    next()
  }
})

export default router