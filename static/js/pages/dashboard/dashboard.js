/* Dashboard charts, drawn from the numbers the server puts in #dashboardData. */
(function () {
  'use strict';
  const data = JSON.parse(document.getElementById('dashboardData').textContent);

  window.addEventListener('load', function () {
    if (!window.Chart) return;

    new Chart(document.getElementById('salesChart').getContext('2d'), {
      type: 'line',
      data: {
        labels: data.chart.map(m => m.label),
        datasets: [{
          label: 'Sales (₹)',
          data: data.chart.map(m => m.sales),
          borderColor: '#0b2f4e',
          backgroundColor: 'rgba(11,47,78,0.1)',
          fill: true,
          tension: 0.4
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } }
      }
    });

    const products = document.getElementById('topProductsChart');
    if (products && data.top_products.length) {
      new Chart(products.getContext('2d'), {
        type: 'doughnut',
        data: {
          labels: data.top_products.map(p => p.product_name),
          datasets: [{
            data: data.top_products.map(p => p.qty),
            backgroundColor: ['#0b2f4e', '#1e4a6f', '#3b6a94', '#ffd966', '#e1e9f0']
          }]
        },
        options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
      });
    }
  });
})();
