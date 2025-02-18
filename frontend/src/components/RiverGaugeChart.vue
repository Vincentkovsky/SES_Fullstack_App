<template>
  <div class="chart-container">
    <Line
      v-if="chartData"
      :data="chartData"
      :options="chartOptions"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  type ScriptableContext
} from 'chart.js';
import { Line } from 'vue-chartjs';
import type { GaugingData } from '../services/api';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const props = defineProps<{
  gaugingData: GaugingData | null;
}>();

const chartData = computed(() => {
  if (!props.gaugingData) return null;

  const timestamps = props.gaugingData.timeseries.map(item => {
    const date = new Date(item.timestamp);
    return date.toLocaleTimeString('en-US', { 
      year: '2-digit', 
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false 
    });
  });

  const depths = props.gaugingData.timeseries.map(item => item.maxDepth);

  return {
    labels: timestamps,
    datasets: [
      {
        label: 'River Depth (m)',
        data: depths,
        borderColor: 'rgba(59, 130, 246, 0.8)',
        backgroundColor: (context: ScriptableContext<'line'>) => {
          const chart = context.chart;
          const { ctx, chartArea } = chart;
          if (!chartArea) return 'rgba(59, 130, 246, 0.1)';  // Fallback color
          
          // Create gradient from top of chart area to bottom
          const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          gradient.addColorStop(0, 'rgba(59, 130, 246, 0.4)');   // More opaque blue at top
          gradient.addColorStop(1, 'rgba(59, 130, 246, 0.05)');  // Almost transparent at bottom
          return gradient;
        },
        borderWidth: 2,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 6,
        pointHoverBackgroundColor: '#3B82F6',
        pointHoverBorderColor: 'white',
        pointHoverBorderWidth: 2,
        fill: true
      }
    ]
  };
});

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false
    },
    tooltip: {
      mode: 'index' as const,
      intersect: false,
      callbacks: {
        label: (context: any) => `Depth: ${context.raw.toFixed(2)}m`
      }
    }
  },
  scales: {
    y: {
      beginAtZero: true,
      title: {
        display: true,
        text: 'Depth (m)'
      },
      grid: {
        color: 'rgba(0, 0, 0, 0.05)',
        drawBorder: false
      }
    },
    x: {
      grid: {
        display: false,
        drawBorder: false
      }
    }
  },
  interaction: {
    intersect: false,
    mode: 'index' as const
  },
  elements: {
    line: {
      tension: 0.4
    }
  }
};
</script>

<style scoped>
.chart-container {
  height: 160px;
  width: 100%;
}
</style> 