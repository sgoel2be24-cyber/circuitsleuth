import type { Candidate } from '../types'

export function CandidateCrops({ inspectionId, candidate }: { inspectionId: string; candidate: Candidate }) {
  const crops = [['reference','Reference'],['aligned_test','Aligned test'],['difference','Difference']] as const
  return <div className="mt-4"><h4 className="text-xs font-semibold text-slate-200">Visual evidence</h4><div className="mt-2 grid grid-cols-3 gap-2">{crops.map(([role,label]) => <figure key={role} className="overflow-hidden rounded-md border border-[#2d404a] bg-[#080e14]"><img src={`/api/inspections/${inspectionId}/candidates/${candidate.region_id}/crop/${role}`} alt={`${label} crop of region ${candidate.region_id}`} className="h-24 w-full object-contain [image-rendering:pixelated]"/><figcaption className="border-t border-[#25333f] px-1 py-1.5 text-center text-[9px] text-slate-300">{label}</figcaption></figure>)}</div><p className="mt-1.5 text-[9px] leading-relaxed text-slate-400">Aligned crops of the original pixels. Magnification adds no optical detail.</p></div>
}
