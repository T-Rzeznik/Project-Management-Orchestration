interface Props {
  contributors: string[]
}

function getAvatarUrl(login: string): string {
  return `https://github.com/${login}.png?size=40`
}

export default function ContributorAvatars({ contributors }: Props) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-gray-500 text-sm">Contributors:</span>
      <div className="flex -space-x-2">
        {contributors.slice(0, 10).map((login) => (
          <a
            key={login}
            href={`https://github.com/${login}`}
            target="_blank"
            rel="noopener noreferrer"
            title={login}
            className="block"
          >
            <img
              src={getAvatarUrl(login)}
              alt={login}
              className="w-8 h-8 rounded-full border-2 border-gray-900 hover:z-10 hover:scale-110 transition-transform"
              onError={(e) => {
                // fallback to initials if avatar fails
                const img = e.currentTarget
                img.style.display = 'none'
              }}
            />
          </a>
        ))}
        {contributors.length > 10 && (
          <div className="w-8 h-8 rounded-full border-2 border-gray-900 bg-gray-700 flex items-center justify-center text-xs text-gray-300">
            +{contributors.length - 10}
          </div>
        )}
      </div>
    </div>
  )
}
