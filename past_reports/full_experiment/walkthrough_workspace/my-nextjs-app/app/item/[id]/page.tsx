import { checkIsAvailable, preload } from '@/lib/data'
import { Item } from '@/components/Item'

export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params

  // Start loading item data immediately
  preload(id)

  // Perform another async task
  const isAvailable = await checkIsAvailable()

  return (
    <div className="p-8">
      {isAvailable ? (
        <Item id={id} />
      ) : (
        <div className="text-red-600 font-semibold">
          This item is currently unavailable
        </div>
      )}
    </div>
  )
}
