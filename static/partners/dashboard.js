document.addEventListener('DOMContentLoaded', () => {
  const items = [...document.querySelectorAll('[data-donor-item]')];
  const search = document.querySelector('[data-donor-search-input]');
  const status = document.querySelector('[data-donor-status-filter]');
  const empty = document.querySelector('[data-dashboard-no-results]');

  const applyFilters = () => {
    if (!items.length) return;
    const needle = (search?.value || '').trim().toLowerCase();
    const selected = status?.value || 'all';
    let visible = 0;
    items.forEach(item => {
      const matchesText = !needle || (item.dataset.donorSearch || '').includes(needle);
      const matchesStatus = selected === 'all' || item.dataset.donorStatus === selected;
      const show = matchesText && matchesStatus;
      item.hidden = !show;
      if (show) visible += 1;
    });
    if (empty) empty.hidden = visible !== 0;
  };

  search?.addEventListener('input', applyFilters);
  status?.addEventListener('change', applyFilters);
  applyFilters();

  document.querySelectorAll('[data-donor-toggle]').forEach(button => {
    const target = document.getElementById(button.getAttribute('aria-controls'));
    if (!target) return;
    button.addEventListener('click', () => {
      const expanded = button.getAttribute('aria-expanded') === 'true';
      button.setAttribute('aria-expanded', String(!expanded));
      target.hidden = expanded;
    });
  });

  document.querySelectorAll('.placement [data-toggle-url]').forEach(input => {
    input.addEventListener('change', () => {
      const placement = input.closest('[data-placement-id]');
      if (!placement) return;
      const summary = document.querySelector(`[data-placement-summary-id="${placement.dataset.placementId}"]`);
      if (!summary) return;
      window.setTimeout(() => summary.classList.toggle('is-disabled', !input.checked), 250);
    });
  });
});
