import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

export function RadarPanel({ data }: { data: Array<{ dim: string; pct: number }> }) {
  return (
    <div className="panel">
      <div className="section-title">Radar · all dimensions (normalized %)</div>
      <ResponsiveContainer width="100%" height={250}>
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke="var(--line)" />
          <PolarAngleAxis dataKey="dim" tick={{ fill: "var(--mut)", fontSize: 11 }} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Radar
            dataKey="pct"
            stroke="var(--accent)"
            fill="var(--accent)"
            fillOpacity={0.25}
            isAnimationActive={false}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
