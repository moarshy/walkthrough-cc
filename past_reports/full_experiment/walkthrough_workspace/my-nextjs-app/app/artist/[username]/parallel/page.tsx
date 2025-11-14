import { getArtist, getAlbums } from '@/lib/data'
import Albums from '../albums'

export default async function Page({
  params,
}: {
  params: Promise<{ username: string }>
}) {
  const { username } = await params

  // Initiate both requests without awaiting
  const artistData = getArtist(username)
  const albumsData = getAlbums(username)

  // Wait for both to complete
  const [artist, albums] = await Promise.all([artistData, albumsData])

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold">{artist.name}</h1>
      <p className="text-gray-600">{artist.bio}</p>
      <Albums list={albums} />
    </div>
  )
}
