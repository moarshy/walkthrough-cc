import { getItem } from '@/lib/data'

export async function Item({ id }: { id: string }) {
  const result = await getItem(id)

  return (
    <div className="p-6 border rounded-lg">
      <h2 className="text-xl font-bold">{result.name}</h2>
      <p className="text-gray-600 mt-2">{result.description}</p>
      <p className="text-lg font-semibold mt-4">${result.price}</p>
    </div>
  )
}
