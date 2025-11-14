import { getItem } from '@/utils/get-item'

async function ItemDetails({ id }: { id: string }) {
  const item = await getItem(id)
  return <div className="text-gray-600">Category: {item.category}</div>
}

async function ItemStock({ id }: { id: string }) {
  const item = await getItem(id)
  return <div className="text-green-600">Stock: {item.stock}</div>
}

export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const item = await getItem(id)

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">{item.name}</h1>
      <ItemDetails id={id} />
      <ItemStock id={id} />
      <p className="mt-4 text-sm text-gray-500">
        Check console - only ONE database query!
      </p>
    </div>
  )
}
