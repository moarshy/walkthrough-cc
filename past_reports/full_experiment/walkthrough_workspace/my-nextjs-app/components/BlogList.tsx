import { getPosts } from '@/lib/data'

export default async function BlogList() {
  // Simulate slow data fetch
  await new Promise(resolve => setTimeout(resolve, 2000))
  const posts = await getPosts()

  return (
    <ul className="space-y-2">
      {posts.map((post: any) => (
        <li key={post.id} className="p-2 border rounded">
          {post.title}
        </li>
      ))}
    </ul>
  )
}
