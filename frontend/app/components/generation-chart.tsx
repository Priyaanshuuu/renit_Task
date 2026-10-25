import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Interval } from "../lib/api";
import { formatHour, formatInstant, formatNumber } from "../lib/format";

export function GenerationChart({
  intervals,
  showActuals,
}: {
  intervals: Interval[];
  showActuals: boolean;
}) {
  // Exclude outcomes entirely before reveal, including from the scale and tooltip.
  const data = intervals.map((item) => ({
    time: formatHour(item.delivery_start),
    forecast: item.forecast_mw,
    publishedAt: item.forecast_published_at,
    ...(showActuals ? { actual: item.actual_mw } : {}),
  }));
  return (
    <div
      className="generation-chart"
      aria-label={
        showActuals
          ? "Forecast and actual hourly generation chart"
          : "Decision-time forecast chart"
      }
    >
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <LineChart
          data={data}
          margin={{ top: 18, right: 12, bottom: 8, left: 0 }}
          accessibilityLayer
        >
          <CartesianGrid stroke="#e7ecee" vertical={false} />
          <XAxis
            dataKey="time"
            tickLine={false}
            axisLine={false}
            minTickGap={35}
            interval="preserveStartEnd"
            tick={{ fill: "#66777d", fontSize: 11 }}
          />
          <YAxis
            width={58}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value: number) => formatNumber(value)}
            tick={{ fill: "#66777d", fontSize: 11 }}
          />
          <Tooltip
            content={({ active, payload }) => {
              const point = payload?.[0]?.payload as
                (typeof data)[number] | undefined;
              if (!active || !point) return null;
              return (
                <div className="chart-tooltip">
                  <strong>{point.time} GMT · MW</strong>
                  <p>Forecast: {formatNumber(point.forecast)}</p>
                  <p>
                    Published:{" "}
                    {point.publishedAt
                      ? formatInstant(point.publishedAt)
                      : "No eligible forecast"}
                  </p>
                  {showActuals && (
                    <p>Actual: {formatNumber(point.actual ?? null)}</p>
                  )}
                </div>
              );
            }}
          />
          <Line
            name="Forecast"
            dataKey="forecast"
            type="linear"
            stroke="#087f78"
            strokeWidth={2.5}
            dot={{ r: 2, strokeWidth: 0, fill: "#087f78" }}
            activeDot={{ r: 4 }}
            connectNulls={false}
            isAnimationActive={false}
          />
          {showActuals && (
            <Line
              name="Actual"
              dataKey="actual"
              type="linear"
              stroke="#bc6a20"
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={{ r: 2, strokeWidth: 0, fill: "#bc6a20" }}
              connectNulls={false}
              isAnimationActive={false}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
