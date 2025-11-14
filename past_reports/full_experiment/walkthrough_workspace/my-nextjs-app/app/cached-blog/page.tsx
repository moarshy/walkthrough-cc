export default async function Page() {
  // Force caching - revalidate every 60 seconds
  const data = await fetch('https://api.vercel.app/blog', {
    next: { revalidate: 60 }
  })
  const posts = await data.json()

  return (
    <div className="p-8">
      <p className="text-sm text-gray-500 mb-4">
        Cached data (revalidates every 60s)
      </p>
      <ul className="space-y-2">
        {posts.map((post: any) => (
          <li key={post.id}>{post.title}</li>
        ))}
      </ul>
    </div>
  )
}
