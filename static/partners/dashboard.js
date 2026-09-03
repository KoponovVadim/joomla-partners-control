document.addEventListener('DOMContentLoaded', () => {
  const items = [...document.querySelectorAll('[data-donor-item]')];
  const search = document.querySelector('[data-donor-search-input]');
  const status = document.querySelector('[data-donor-status-filter]');
  const empty = document.querySelector('[data-dashboard-no-results]');
  const expandedStorageKey = 'jpc-expanded-donors';
  const focusStorageKey = 'jpc-focus-donor';
  const clientPalette = [
    ['#5b7fa3', '#f3f7fb'],
    ['#5f8f82', '#f2f8f6'],
    ['#7b72a8', '#f6f4fa'],
    ['#a57a58', '#faf6f2'],
    ['#a56578', '#faf3f5'],
    ['#6f8b5e', '#f5f8f2'],
    ['#5f8797', '#f2f7f9'],
    ['#8c7658', '#f8f5f1'],
    ['#687ba8', '#f3f5fa'],
    ['#8a8d5f', '#f7f7f2'],
    ['#8a6d95', '#f7f3f8'],
    ['#667f76', '#f3f7f5'],
  ];

  const colorIndexForKey = key => {
    let hash = 2166136261;
    for (let index = 0; index < key.length; index += 1) {
      hash ^= key.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0) % clientPalette.length;
  };

  document.querySelectorAll('[data-client-key]').forEach(element => {
    const key = (element.dataset.clientKey || '').trim().toLowerCase();
    if (!key) return;
    const [accent, tint] = clientPalette[colorIndexForKey(key)];
    element.style.setProperty('--client-accent', accent);
    element.style.setProperty('--client-tint', tint);
  });

  let expandedDonors = new Set();
  try {
    expandedDonors = new Set(JSON.parse(sessionStorage.getItem(expandedStorageKey) || '[]'));
  } catch (error) {
    sessionStorage.removeItem(expandedStorageKey);
  }

  const persistExpandedDonors = () => {
    sessionStorage.setItem(expandedStorageKey, JSON.stringify([...expandedDonors]));
  };

  const setExpanded = (item, expanded) => {
    const button = item.querySelector('[data-donor-toggle]');
    const target = button ? document.getElementById(button.getAttribute('aria-controls')) : null;
    if (!button || !target) return;

    button.setAttribute('aria-expanded', String(expanded));
    target.hidden = !expanded;

    const donorId = item.dataset.donorId;
    if (!donorId) return;
    if (expanded) expandedDonors.add(donorId);
    else expandedDonors.delete(donorId);
    persistExpandedDonors();
  };

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

  items.forEach(item => {
    const donorId = item.dataset.donorId;
    const button = item.querySelector('[data-donor-toggle]');
    if (!button) return;

    if (donorId && expandedDonors.has(donorId)) {
      setExpanded(item, true);
    }

    button.addEventListener('click', () => {
      setExpanded(item, button.getAttribute('aria-expanded') !== 'true');
    });
  });

  document.querySelectorAll('.add-placement').forEach(form => {
    form.addEventListener('submit', () => {
      const item = form.closest('[data-donor-id]');
      const donorId = item?.dataset.donorId;
      if (!donorId) return;
      expandedDonors.add(donorId);
      persistExpandedDonors();
      sessionStorage.setItem(focusStorageKey, donorId);
    });
  });

  const focusDonorId = sessionStorage.getItem(focusStorageKey);
  if (focusDonorId) {
    const item = items.find(candidate => candidate.dataset.donorId === focusDonorId);
    if (item) {
      setExpanded(item, true);
      window.requestAnimationFrame(() => {
        item.scrollIntoView({block: 'center'});
      });
    }
    sessionStorage.removeItem(focusStorageKey);
  }

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
