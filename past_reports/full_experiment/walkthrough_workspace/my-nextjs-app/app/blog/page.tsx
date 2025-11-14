import { Suspense } from 'react'
import BlogList from '@/components/BlogList'
import BlogListSkeleton from '@/components/BlogListSkeleton'

export default function BlogPage() {
  return (
    <div className="p-8">
      <header className="mb-6">
        <h1 className="text-3xl font-bold">Welcome to the Blog</h1>
        <p className="text-gray-600">Read the latest posts below.</p>
      </header>
      <main>
        <Suspense fallback={<BlogListSkeleton />}>
          <BlogList />
        </Suspense>
      </main>
    </div>
  )
}
