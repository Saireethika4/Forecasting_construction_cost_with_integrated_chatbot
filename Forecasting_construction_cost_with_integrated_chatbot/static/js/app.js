// Menu toggles and scroll reveals shared by every page
document.querySelectorAll('[data-toggle]').forEach((button) => {
  const target = document.getElementById(button.dataset.toggle);
  const scrim = document.getElementById('scrim');
  const setOpen = (open) => {
    target.classList.toggle('is-open', open);
    if (scrim) scrim.classList.toggle('is-open', open);
    button.setAttribute('aria-expanded', String(open));
  };
  button.addEventListener('click', () => setOpen(!target.classList.contains('is-open')));
  if (scrim) scrim.addEventListener('click', () => setOpen(false));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && target.classList.contains('is-open')) {
      setOpen(false);
      button.focus();
    }
  });
});

const revealed = document.querySelectorAll('.reveal');
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-in');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });
  revealed.forEach((element) => observer.observe(element));
} else {
  revealed.forEach((element) => element.classList.add('is-in'));
}
