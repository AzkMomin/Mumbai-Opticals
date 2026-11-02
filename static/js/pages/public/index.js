// subtle simulation: clicking any brand shows an alert with brand name
// (to illustrate that it would show all available stocks of that brand)
// This matches requirement: "when user clicks under its respective sections it will show all the available stocks of the selected brand."
document.querySelectorAll('.brand-item').forEach(item => {
  item.addEventListener('click', function(e) {
    e.preventDefault();
    const brand = this.innerText.trim();
    // find parent section (specs or watches)
    const parentCard = this.closest('.category-card');
    const category = parentCard ? parentCard.querySelector('.category-header')?.innerText : 'collection';
    alert(`🔍 Show all available stocks for ${brand} (${category}) — (simulated page)`);
  });
});
