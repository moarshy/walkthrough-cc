import { Suspense } from 'react'
import { getArtist, getArtistPlaylists } from '@/lib/data'

async function Playlists({ artistID }: { artistID: string }) {
  const playlists = await getArtistPlaylists(artistID)

  return (
    <ul className="mt-4 space-y-2">
      {playlists.map((playlist) => (
        <li key={playlist.id} className="p-2 bg-blue-50 rounded">
          {playlist.name}
        </li>
      ))}
    </ul>
  )
}

export default async function Page({
  params,
}: {
  params: Promise<{ username: string }>
}) {
  const { username } = await params
  const artist = await getArtist(username)

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold">{artist.name}</h1>
      <Suspense fallback={<div>Loading playlists...</div>}>
        <Playlists artistID={artist.id} />
      </Suspense>
    </div>
  )
}
