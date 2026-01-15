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
  Filler,
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
  Legend,
  Filler
);

const props = defineProps<{
  gaugingData: GaugingData | null;
}>();

const chartData = computed(() => {
  if (!props.gaugingData) return null;

  // Format timestamps as precise date and time labels
  const timestamps = props.gaugingData.timestamps;
  
  const dateLabels = timestamps.map((timestamp) => {
    const date = new Date(timestamp);
    // Format as "MM/DD HH:mm"
    return date.toLocaleString('en-US', { 
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false 
    });
  });

  const values = props.gaugingData.values;
  
  // Enhanced blue color scheme matching the image
  const lineColor = 'rgb(91, 143, 219)'; // #5B8FDB - deeper blue
  const fillColorTop = 'rgba(91, 143, 219, 0.6)';
  const fillColorBottom = 'rgba(173, 201, 242, 0.2)';

  return {
    labels: dateLabels,
    datasets: [
      {
        label: 'Water Level (m)',
        data: values,
        borderColor: lineColor,
        backgroundColor: (context: ScriptableContext<'line'>) => {
          const chart = context.chart;
          const { ctx, chartArea } = chart;
          if (!chartArea) return fillColorTop;
          
          const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          gradient.addColorStop(0, fillColorTop);
          gradient.addColorStop(0.5, 'rgba(135, 173, 230, 0.35)');
          gradient.addColorStop(1, fillColorBottom);
          return gradient;
        },
        borderWidth: 2.5,
        tension: 0.45,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: lineColor,
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
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      titleColor: '#1f2937',
      bodyColor: '#4b5563',
      borderColor: 'rgba(209, 213, 219, 0.4)',
      borderWidth: 1,
      padding: 10,
      displayColors: false,
      callbacks: {
        title: (context: any) => {
          const index = context[0].dataIndex;
          const timestamp = props.gaugingData?.timestamps[index];
          if (timestamp) {
            const date = new Date(timestamp);
            return date.toLocaleString('en-US', { 
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
              hour12: false 
            });
          }
          return '';
        },
        label: (context: any) => {
          const value = context.raw.toFixed(2);
          return `${value} m`;
        }
      }
    }
  },
  scales: {
    y: {
      beginAtZero: true,
      title: {
        display: true,
        text: 'Water Depth (m)',
        color: '#4b5563',
        font: {
          size: 12,
          weight: '600'
        },
        padding: {
          bottom: 8
        }
      },
      ticks: {
        stepSize: 2, // Show ticks every 2 meters (0, 2, 4, 6, 8, 10...)
        callback: function(value: any) {
          return value;
        },
        color: '#6b7280',
        font: {
          size: 11
        }
      },
      grid: {
        color: 'rgba(209, 213, 219, 0.3)',
        drawBorder: false,
        lineWidth: 1
      },
      border: {
        display: false
      }
    },
    x: {
      ticks: {
        color: '#6b7280',
        font: {
          size: 10
        },
        maxRotation: 45,
        minRotation: 45,
        autoSkip: true,
        maxTicksLimit: 12 // Show up to 12 labels to avoid crowding
      },
      grid: {
        display: false,
        drawBorder: false
      },
      border: {
        display: false
      }
    }
  },
  interaction: {
    intersect: false,
    mode: 'index' as const
  },
  elements: {
    line: {
      tension: 0.45
    }
  }
}));
</script>

<style scoped>
.chart-container {
  height: 220px;
  width: 100%;
  display: flex;
  flex-direction: column;
  padding-bottom: 10px;
}
</style> 