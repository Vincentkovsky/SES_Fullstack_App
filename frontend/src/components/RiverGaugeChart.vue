<template>
  <div class="chart-container">
    <div class="tabs">
      <button 
        class="tab-button" 
        :class="{ active: activeTab === 'waterLevel' }"
        @click="activeTab = 'waterLevel'"
      >
        Water Level
      </button>
      <button 
        class="tab-button" 
        :class="{ active: activeTab === 'flowRate' }"
        @click="activeTab = 'flowRate'"
      >
        Flow Rate
      </button>
    </div>
    <Line
      v-if="chartData"
      :data="chartData"
      :options="chartOptions"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
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

const activeTab = ref<'waterLevel' | 'flowRate'>('waterLevel');

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

  const values = props.gaugingData.timeseries.map(item => 
    activeTab.value === 'waterLevel' ? item.waterLevel : item.flowRate
  );

  const label = activeTab.value === 'waterLevel' ? 'Water Level (m)' : 'Flow Rate (ML/day)';
  const color = activeTab.value === 'waterLevel' ? '59, 130, 246' : '234, 88, 12'; // Blue for water level, Orange for flow rate

  return {
    labels: timestamps,
    datasets: [
      {
        label,
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
        pointHoverBackgroundColor: activeTab.value === 'waterLevel' ? '#3B82F6' : '#EA580C',
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
          return activeTab.value === 'waterLevel' 
            ? `Water Level: ${value}m`
            : `Flow Rate: ${value}ML/day`;
        }
      }
    }
  },
  scales: {
    y: {
      beginAtZero: true,
      title: {
        display: true,
        text: activeTab.value === 'waterLevel' ? 'Water Level (m)' : 'Flow Rate (ML/day)'
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

.tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.tab-button {
  padding: 0.5rem 1rem;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 0.375rem;
  background-color: white;
  color: #4b5563;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-button:hover {
  background-color: #f9fafb;
}

.tab-button.active {
  background-color: #f3f4f6;
  border-color: rgba(0, 0, 0, 0.2);
  color: #1f2937;
}
</style> 