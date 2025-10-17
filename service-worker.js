const CACHE_NAME = 'course-go-cache-v1';
// Liste des fichiers essentiels au fonctionnement de l'appli
const URLS_TO_CACHE = [
  '/', // La page d'accueil (index2.html)
  '/api/v1/magasin_data/M001', // Les données du plan
  '/static/icon.png' // L'icône
];

// Étape d'installation : on met les fichiers en cache
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Cache ouvert');
        return cache.addAll(URLS_TO_CACHE);
      })
  );
});

// Étape d'activation : on nettoie les anciens caches si nécessaire (pour les mises à jour)
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Étape de fetch : on intercepte les requêtes réseau
self.addEventListener('fetch', event => {
  event.respondWith(
    // On essaie d'abord de récupérer la ressource depuis le réseau
    fetch(event.request).catch(() => {
      // Si le réseau échoue (mode hors-ligne), on cherche dans le cache
      return caches.match(event.request);
    })
  );
});