export default function Albums({
  list
}: {
  list: { id: string; title: string; year: number }[]
}) {
  return (
    <div className="mt-4">
      <h2 className="text-xl font-semibold mb-2">Albums</h2>
      <div className="grid grid-cols-2 gap-4">
        {list.map((album) => (
          <div key={album.id} className="p-4 border rounded">
            <div className="font-medium">{album.title}</div>
            <div className="text-sm text-gray-500">{album.year}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
