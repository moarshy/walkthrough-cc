import { cache } from 'react'
import 'server-only'

// Simulate database query
const fetchItemFromDB = async (id: string) => {
  console.log(`[DB Query] Fetching item ${id}`)
  await new Promise(resolve => setTimeout(resolve, 1000))
  return {
    id,
    name: `Database Item ${id}`,
    category: 'Electronics',
    stock: 42
  }
}

export const preload = (id: string) => {
  void getItem(id)
}

export const getItem = cache(async (id: string) => {
  return fetchItemFromDB(id)
})
