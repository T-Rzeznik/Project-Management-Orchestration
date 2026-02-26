interface Props {
  stack: string[]
}

const langColors: Record<string, string> = {
  Python: 'bg-blue-900/60 text-blue-300 border-blue-700',
  TypeScript: 'bg-blue-800/60 text-blue-200 border-blue-600',
  JavaScript: 'bg-yellow-900/60 text-yellow-300 border-yellow-700',
  Rust: 'bg-orange-900/60 text-orange-300 border-orange-700',
  Go: 'bg-cyan-900/60 text-cyan-300 border-cyan-700',
  Java: 'bg-red-900/60 text-red-300 border-red-700',
  'C++': 'bg-pink-900/60 text-pink-300 border-pink-700',
  C: 'bg-gray-800/60 text-gray-300 border-gray-600',
  Ruby: 'bg-red-800/60 text-red-200 border-red-600',
  Kotlin: 'bg-purple-900/60 text-purple-300 border-purple-700',
  Swift: 'bg-orange-800/60 text-orange-200 border-orange-600',
}

const defaultColor = 'bg-gray-800/60 text-gray-300 border-gray-700'

export default function TechStackBadges({ stack }: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      {stack.map((tech) => (
        <span
          key={tech}
          className={`text-xs px-2.5 py-1 rounded-full border font-medium ${langColors[tech] ?? defaultColor}`}
        >
          {tech}
        </span>
      ))}
    </div>
  )
}
