// assets/charts.js
(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var success = style.getPropertyValue('--success').trim();
  var warning = style.getPropertyValue('--warning').trim();
  var danger = style.getPropertyValue('--danger').trim();

  // --- Chart: Radar - 项目健康度 ---
  var radarChart = echarts.init(document.getElementById('chart-radar'), null, { renderer: 'svg' });
  radarChart.setOption({
    animation: false,
    tooltip: {
      appendToBody: true,
      trigger: 'item'
    },
    radar: {
      indicator: [
        { name: 'CI/构建', max: 100 },
        { name: '版本一致性', max: 100 },
        { name: '许可合规', max: 100 },
        { name: '发布规范', max: 100 },
        { name: '文档质量', max: 100 },
        { name: '包管理', max: 100 }
      ],
      radius: '65%',
      center: ['50%', '55%'],
      splitNumber: 4,
      axisName: {
        color: ink,
        fontSize: 13,
        fontWeight: 500
      },
      splitLine: {
        lineStyle: {
          color: rule
        }
      },
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(255,255,255,0.5)', 'rgba(248,250,252,0.3)']
        }
      },
      axisLine: {
        lineStyle: {
          color: rule
        }
      }
    },
    series: [{
      type: 'radar',
      data: [
        {
          value: [95, 100, 60, 40, 85, 20],
          name: '当前状态',
          areaStyle: {
            color: {
              type: 'radial',
              x: 0.5, y: 0.5, r: 0.5,
              colorStops: [
                { offset: 0, color: accent + '40' },
                { offset: 1, color: accent2 + '20' }
              ]
            }
          },
          lineStyle: {
            color: accent,
            width: 2
          },
          itemStyle: {
            color: accent
          },
          symbol: 'circle',
          symbolSize: 6
        }
      ]
    }]
  });
  window.addEventListener('resize', function() { radarChart.resize(); });

  // --- Chart: Pie - 问题分布 ---
  var pieChart = echarts.init(document.getElementById('chart-pie'), null, { renderer: 'svg' });
  pieChart.setOption({
    animation: false,
    tooltip: {
      appendToBody: true,
      trigger: 'item',
      formatter: '{b}: {c} 项 ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      textStyle: {
        color: ink,
        fontSize: 13
      },
      itemGap: 12
    },
    series: [
      {
        name: '问题严重程度',
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold',
            color: ink
          }
        },
        labelLine: {
          show: false
        },
        data: [
          { value: 1, name: 'P0 严重', itemStyle: { color: danger } },
          { value: 2, name: 'P1 中优先级', itemStyle: { color: warning } },
          { value: 3, name: 'P2 低优先级', itemStyle: { color: accent } },
          { value: 4, name: 'P3 优化建议', itemStyle: { color: accent2 } }
        ]
      }
    ]
  });
  window.addEventListener('resize', function() { pieChart.resize(); });

})();
