import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/auth'
import { Layout } from './components/Layout'
import { Login } from './pages/auth/Login'
import { TwoFASetup } from './pages/auth/TwoFASetup'
import { TwoFAVerify } from './pages/auth/TwoFAVerify'
import { Dashboard } from './pages/Dashboard'
import { HostsList } from './pages/inventory/HostsList'
import { HostDetail } from './pages/inventory/HostDetail'
import { RelationshipsList } from './pages/inventory/RelationshipsList'
import { RelationshipDetail } from './pages/inventory/RelationshipDetail'
import { ApplicationsList } from './pages/inventory/ApplicationsList'
import { ClustersList } from './pages/inventory/ClustersList'
import { NamespacesList } from './pages/inventory/NamespacesList'
import { ServicesList } from './pages/inventory/ServicesList'
import { ReconciliationList } from './pages/reconciliation/ReconciliationList'
import { ReconciliationDetail } from './pages/reconciliation/ReconciliationDetail'
import { CertificationQueue } from './pages/certification/CertificationQueue'
import { CertificationDetail } from './pages/certification/CertificationDetail'
import { AdminSettings } from './pages/admin/AdminSettings'
import { AdminUsers } from './pages/admin/AdminUsers'
import { AdminRelationshipTypes } from './pages/admin/AdminRelationshipTypes'
import { AdminAssetTypes } from './pages/admin/AdminAssetTypes'
import { AdminEnvironments } from './pages/admin/AdminEnvironments'
import { AdminStatuses } from './pages/admin/AdminStatuses'
import { AdminCriticities } from './pages/admin/AdminCriticities'
import { AdminOperatingSystems } from './pages/admin/AdminOperatingSystems'
import { AdminAreas } from './pages/admin/AdminAreas'
import { Profile } from './pages/Profile'
import { NotFound } from './pages/NotFound'

function ProtectedRoute({ children, allowedRoles = [] }: { children: React.ReactNode; allowedRoles?: string[] }) {
  const { isAuthenticated, user, isLoading } = useAuthStore()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (allowedRoles.length > 0 && user && !allowedRoles.some(role => user.roles.includes(role))) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthStore()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent"></div>
      </div>
    )
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

function App() {
  const { checkAuth } = useAuthStore()

  // Check auth on app load
  React.useEffect(() => {
    checkAuth()
  }, [checkAuth])

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
      <Route path="/2fa/setup" element={<ProtectedRoute><TwoFASetup /></ProtectedRoute>} />
      <Route path="/2fa/verify" element={<PublicRoute><TwoFAVerify /></PublicRoute>} />

      {/* Protected routes */}
      <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<Dashboard />} />
        <Route path="profile" element={<Profile />} />
        
        {/* Inventory */}
        <Route path="hosts" element={<HostsList />} />
        <Route path="hosts/:id" element={<HostDetail />} />
        <Route path="relationships" element={<RelationshipsList />} />
        <Route path="relationships/:id" element={<RelationshipDetail />} />
        <Route path="applications" element={<ApplicationsList />} />
        <Route path="clusters" element={<ClustersList />} />
        <Route path="namespaces" element={<NamespacesList />} />
        <Route path="services" element={<ServicesList />} />
        
        {/* Reconciliation */}
        <Route path="reconciliation" element={<ReconciliationList />} />
        <Route path="reconciliation/:id" element={<ReconciliationDetail />} />
        
        {/* Certification */}
        <Route path="certification" element={<CertificationQueue />} />
        <Route path="certification/:id" element={<CertificationDetail />} />
        
        {/* Admin */}
        <Route path="admin" element={<AdminSettings />} />
        <Route path="admin/users" element={<AdminUsers />} />
        <Route path="admin/relationship-types" element={<AdminRelationshipTypes />} />
        <Route path="admin/asset-types" element={<AdminAssetTypes />} />
        <Route path="admin/environments" element={<AdminEnvironments />} />
        <Route path="admin/statuses" element={<AdminStatuses />} />
        <Route path="admin/criticities" element={<AdminCriticities />} />
        <Route path="admin/operating-systems" element={<AdminOperatingSystems />} />
        <Route path="admin/areas" element={<AdminAreas />} />
      </Route>

      {/* 404 */}
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}

export default App