/**
 * MediCare+ Clinic Management System
 * Interactive Client-Side Features
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. One-Click Demo Credentials Autofill
  const demoButtons = document.querySelectorAll('.demo-pill-btn');
  demoButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const role = btn.dataset.role;
      const username = btn.dataset.username;
      const password = btn.dataset.password;

      const roleSelect = document.querySelector('select[name="role"]');
      const userInput = document.querySelector('input[name="username"]');
      const passInput = document.querySelector('input[name="password"]');

      if (roleSelect && userInput && passInput) {
        roleSelect.value = role;
        userInput.value = username;
        passInput.value = password;
        
        // Highlight active button
        demoButtons.forEach(b => b.style.borderColor = '#cbd5e1');
        btn.style.borderColor = '#0284c7';
      }
    });
  });

  // 2. Real-time Live Filter for Data Tables
  const searchInput = document.getElementById('tableSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase().trim();
      const rows = document.querySelectorAll('table.data-table tbody tr');

      rows.forEach(row => {
        const text = row.innerText.toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
      });
    });
  }

  // 3. Auto-dismiss flash alerts after 5 seconds
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-8px)';
      setTimeout(() => alert.remove(), 400);
    }, 6000);
  });
});
