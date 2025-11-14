export default function BlogListSkeleton() {
  return (
    <div className="space-y-2">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-12 bg-gray-200 animate-pulse rounded"></div>
      ))}
    </div>
  )
}
