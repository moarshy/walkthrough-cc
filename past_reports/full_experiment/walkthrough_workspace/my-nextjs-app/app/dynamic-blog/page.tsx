export default async function Page() {
  // Force dynamic rendering - no caching
  const data = await fetch('https://api.vercel.app/blog', {
    cache: 'no-store'
  })
  const posts = await data.json()

  return (
    <div className="p-8">
      <p className="text-sm text-gray-500 mb-4">
        Fetched at: {new Date().toLocaleTimeString()}
      </p>
      <ul className="space-y-2">
        {posts.map((post: any) => (
          <li key={post.id}>{post.title}</li>
        ))}
      </ul>
    </div>
  )
}
