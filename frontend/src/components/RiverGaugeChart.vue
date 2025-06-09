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

  // Parse timestamps to display in a more readable format
  const timestamps = props.gaugingData.timestamps.map(timestamp => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      year: '2-digit', 
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false 
    });
  });

  const values = props.gaugingData.values;
  const color = '59, 130, 246'; // Blue for water level

  return {
    labels: timestamps,
    datasets: [
      {
        label: 'Water Level (m)',
        data: values,
        borderColor: `rgba(${color}, 0.8)`,
        backgroundColor: (context: ScriptableContext<'line'>) => {
          const chart = context.chart;
          const { ctx, chartArea } = chart;
          if (!chartArea) return `rgba(${color}, 0.1)`;
          
          const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          gradient.addColorStop(0, `rgba(${color}, 0.4)`);
          gradient.addColorStop(1, `rgba(${color}, 0.05)`);
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

const chartOptions = computed(() => ({
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
        label: (context: any) => {
          const value = context.raw.toFixed(2);
          return `Water Level: ${value}m`;
        }
      }
    }
  },
  scales: {
    y: {
      beginAtZero: true,
      title: {
        display: true,
        text: 'Water Level (m)'
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
}));
</script>

<style scoped>
.chart-container {
  height: 200px;
  width: 100%;
  display: flex;
  flex-direction: column;
}
</style> 