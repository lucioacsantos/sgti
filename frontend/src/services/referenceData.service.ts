import { api } from './api'

export interface ReferenceItem {
  id?: number
  name: string
  code?: string
  description?: string
  is_active?: boolean
}

export type ReferenceCategory = 
  | 'asset-types'
  | 'environments'
  | 'locations'
  | 'operational-status'
  | 'manufacturers'

export const referenceDataService = {
  async getAll(category: ReferenceCategory): Promise<ReferenceItem[]> {
    const response = await api.get(`/reference-data/${category}`)
    return response.data
  },

  async create(category: ReferenceCategory, data: Partial<ReferenceItem>): Promise<ReferenceItem> {
    const response = await api.post(`/reference-data/${category}`, data)
    return response.data
  },

  async update(category: ReferenceCategory, id: number, data: Partial<ReferenceItem>): Promise<ReferenceItem> {
    const response = await api.put(`/reference-data/${category}/${id}`, data)
    return response.data
  },

  async delete(category: ReferenceCategory, id: number): Promise<void> {
    await api.delete(`/reference-data/${category}/${id}`)
  }
}