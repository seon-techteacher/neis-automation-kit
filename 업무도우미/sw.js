// 업무도우미 서비스 워커 · © 2026 Kang SeongHo
// 앱 파일을 저장해 두어 인터넷이 끊겨도 열리게 한다. 서비스 워커 자체가 바뀌면 '새 버전' 안내를 띄운다.
// 버전을 올릴 때 version.js와 함께 CACHE 이름을 바꾼다.
const CACHE = 'udesk-0.5.0';
const FILES = [
  './', 'index.html', 'common.css', 'common.js', 'quickcheck.js', 'version.js', 'manifest.webmanifest', 'icon.svg',
  'tools/seat.html', 'tools/check.html', 'tools/docs.html', 'tools/roster.html', 'tools/grade.html', 'tools/class.html', 'tools/score.html', 'tools/image.html', 'tools/exam.html'
];

self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES))); });
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('udesk-') && !k.startsWith(CACHE)).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('message', e => { if (e.data === 'skipWaiting') self.skipWaiting(); });

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  if (url.origin !== location.origin) {
    // 글꼴·라이브러리 CDN만 한 번 받아 두고 다시 쓴다. 유콜 같은 다른 요청은 건드리지 않는다.
    if (/^(cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com|fonts\.(googleapis|gstatic)\.com)$/.test(url.hostname)) {
      e.respondWith(caches.open(CACHE + '-cdn').then(async c => {
        const hit = await c.match(e.request);
        if (hit) return hit;
        const res = await fetch(e.request);
        if (res.ok || res.type === 'opaque') c.put(e.request, res.clone());
        return res;
      }));
    }
    return;
  }
  // 앱 파일은 인터넷이 되면 항상 새로 받고(업데이트 바로 반영), 안 되면 저장해 둔 것을 쓴다.
  e.respondWith(fetch(e.request).then(res => {
    if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); }
    return res;
  }).catch(() => caches.match(e.request, { ignoreSearch: true })));
});
