import type { Milestone } from '../types'

interface Props {
  milestones: Milestone[]
}

export default function MilestoneList({ milestones }: Props) {
  return (
    <div className="space-y-3">
      {milestones.map((m, i) => (
        <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex gap-4 items-start">
          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-indigo-900/60 border border-indigo-700 text-indigo-300 font-bold text-sm shrink-0 mt-0.5">
            {i + 1}
          </div>
          <div>
            <h3 className="font-semibold text-white">{m.title}</h3>
            <p className="text-gray-400 text-sm mt-1">{m.description}</p>
          </div>
        </div>
      ))}
    </div>
  )
}
