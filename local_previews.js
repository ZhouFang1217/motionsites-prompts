/* Local files only: this library never downloads media or uploads selected files. */
(function () {
  'use strict';

  const EXTENSIONS = /\.(mp4|webm|mov|m4v|ogv|ogg)$/i;
  const normalize = value => String(value).normalize('NFKC').toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]/g, '');

  class LocalPreviewLibrary {
    constructor(records, bundled, onChange) {
      this.ids = new Set(records.map(record => record.id));
      this.names = new Map();
      this.bundled = bundled || {};
      this.onChange = onChange;
      this.db = null;
      this.savedIds = new Set();
      this.sessionFiles = new Map();
      this.sessionOnlyIds = new Set();
      this.storageMessage = '';
      records.forEach(record => {
        [record.id, record.title].forEach(name => {
          const key = normalize(name);
          if (!this.names.has(key)) this.names.set(key, new Set());
          this.names.get(key).add(record.id);
        });
      });
    }

    async init() {
      try {
        if (!window.indexedDB) throw new Error('IndexedDB unavailable');
        this.db = await new Promise((resolve, reject) => {
          const request = indexedDB.open('motionsites-local-previews', 1);
          request.onupgradeneeded = () => request.result.createObjectStore('previews', { keyPath: 'id' });
          request.onsuccess = () => resolve(request.result);
          request.onerror = () => reject(request.error);
          request.onblocked = () => reject(new Error('Storage upgrade blocked'));
        });
        this.db.onversionchange = () => {
          this.db.close();
          this.db = null;
          this.storageMessage = '本机缓存连接已关闭，重新打开页面后可继续保存。';
          this.onChange();
        };
        const keys = await new Promise((resolve, reject) => {
          const request = this.db.transaction('previews').objectStore('previews').getAllKeys();
          request.onsuccess = () => resolve(request.result);
          request.onerror = () => reject(request.error);
        });
        this.savedIds = new Set(keys.filter(id => this.ids.has(id)));
      } catch (error) {
        if (this.db) this.db.close();
        this.db = null;
        this.storageMessage = '当前浏览器无法保存缓存；导入的视频仅本次打开可用，刷新后需重新选择。';
      }
      this.onChange();
    }

    has(id) {
      return this.sessionFiles.has(id) || (this.db && this.savedIds.has(id)) || Object.hasOwn(this.bundled, id);
    }

    count() {
      return [...this.ids].filter(id => this.has(id)).length;
    }

    countsByKind() {
      const counts = { video: 0, image: 0 };
      for (const id of this.ids) {
        if (!this.has(id)) continue;
        const imported = this.sessionFiles.has(id) || (this.db && this.savedIds.has(id));
        counts[!imported && this.bundled[id]?.kind === 'image' ? 'image' : 'video']++;
      }
      return counts;
    }

    poster(id) {
      const path = this.bundled[id]?.poster;
      return path && /^media\/[a-z0-9-]+\.(png|jpg|jpeg|webp|gif|avif)$/i.test(path) ? path : null;
    }

    match(file) {
      if (!EXTENSIONS.test(file.name)) return null;
      const parts = (file.webkitRelativePath || file.name).replace(/\\/g, '/').split('/');
      const stem = file.name.replace(/\.[^.]+$/, '');
      if (this.ids.has(stem)) return stem;
      if (this.ids.has(parts[parts.length - 2])) return parts[parts.length - 2];
      let candidates = this.names.get(normalize(stem));
      if (!candidates || candidates.size === 0) candidates = this.names.get(normalize(parts[parts.length - 2] || ''));
      return candidates?.size === 1 ? [...candidates][0] : null;
    }

    async importFiles(files) {
      const groups = new Map();
      const report = { imported: 0, saved: 0, sessionOnly: 0, unmatched: [], duplicates: [], errors: [] };
      for (const file of files) {
        const id = this.match(file);
        if (!id) {
          report.unmatched.push(file.name);
          continue;
        }
        if (!groups.has(id)) groups.set(id, []);
        groups.get(id).push(file);
      }
      for (const [id, candidates] of groups) {
        if (candidates.length !== 1) {
          report.duplicates.push(id);
          continue;
        }
        const file = candidates[0];
        this.sessionFiles.set(id, file);
        report.imported++;
        if (this.db) {
          try {
            await new Promise((resolve, reject) => {
              const transaction = this.db.transaction('previews', 'readwrite');
              transaction.objectStore('previews').put({ id, blob: file, name: file.name, bytes: file.size });
              transaction.oncomplete = resolve;
              transaction.onerror = () => reject(transaction.error);
              transaction.onabort = () => reject(transaction.error || new Error('Storage write aborted'));
            });
            this.savedIds.add(id);
            this.sessionOnlyIds.delete(id);
            report.saved++;
          } catch (error) {
            this.sessionOnlyIds.add(id);
            report.sessionOnly++;
            report.errors.push(`${file.name}：未保存到本机缓存（可能空间不足），仅本次打开可用。`);
          }
        } else {
          this.sessionOnlyIds.add(id);
          report.sessionOnly++;
        }
      }
      this.onChange();
      return report;
    }

    async get(id) {
      if (this.sessionFiles.has(id)) return { blob: this.sessionFiles.get(id) };
      if (this.savedIds.has(id) && this.db) {
        const record = await new Promise((resolve, reject) => {
          const request = this.db.transaction('previews').objectStore('previews').get(id);
          request.onsuccess = () => resolve(request.result);
          request.onerror = () => reject(request.error);
        });
        if (record?.blob instanceof Blob) return { blob: record.blob };
      }
      const relative = this.bundled[id]?.path;
      if (relative && /^media\/[a-z0-9-]+\.(mp4|webm|mov|m4v|ogv|ogg)$/i.test(relative)) {
        return { url: relative, kind: 'video' };
      }
      if (relative && /^media\/[a-z0-9-]+\.(png|jpg|jpeg|webp|gif|avif)$/i.test(relative)) {
        return { url: relative, kind: 'image' };
      }
      return null;
    }
  }

  class LocalCardPreview {
    constructor(getSource, isAllowed = () => true) {
      this.getSource = getSource;
      this.isAllowed = isAllowed;
      this.card = null;
      this.container = null;
      this.video = null;
      this.objectUrl = null;
      this.request = 0;
      this.observer = typeof IntersectionObserver === 'function' ? new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (!entry.isIntersecting && entry.target === this.container) this.stop();
        }
      }) : null;
    }

    stopFor(card) {
      if (this.card === card) this.stop();
    }

    stop() {
      this.request++;
      if (this.container) this.observer?.unobserve(this.container);
      this.card = null;
      this.container = null;
      if (this.video) {
        this.video.onplaying = null;
        this.video.onerror = null;
        this.video.pause();
        this.video.removeAttribute('src');
        this.video.load();
        this.video.remove();
        this.video = null;
      }
      if (this.objectUrl) URL.revokeObjectURL(this.objectUrl);
      this.objectUrl = null;
    }

    async play(card, container, status, id) {
      if (this.card === card || !this.isAllowed()) return;
      this.stop();
      const request = this.request;
      this.card = card;
      this.container = container;
      this.observer?.observe(container);
      status.hidden = true;
      status.textContent = '';
      const fail = error => {
        if (request !== this.request) return;
        status.textContent = error.name === 'NotAllowedError'
          ? '浏览器未允许自动播放，可点击“本地预览”播放。'
          : '悬停预览无法播放，请点击“本地预览”查看详情。';
        status.hidden = false;
        console.warn('Local card preview failed', id, error);
        this.stop();
      };
      try {
        const source = await this.getSource(id);
        if (request !== this.request) return;
        if (!this.isAllowed() || !card.isConnected || !source || source.kind === 'image') {
          this.stop();
          return;
        }
        const video = document.createElement('video');
        video.className = 'card-hover-video';
        video.muted = true;
        video.defaultMuted = true;
        video.playsInline = true;
        video.loop = true;
        video.preload = 'none';
        video.tabIndex = -1;
        video.setAttribute('aria-hidden', 'true');
        video.onplaying = () => {
          if (request === this.request) video.classList.add('is-playing');
        };
        video.onerror = () => fail(new Error(`Media decode error: ${video.error?.code || 'unknown'}`));
        this.video = video;
        this.objectUrl = source.blob ? URL.createObjectURL(source.blob) : null;
        video.src = this.objectUrl || source.url;
        container.appendChild(video);
        await video.play();
        if (request !== this.request) video.pause();
      } catch (error) {
        fail(error);
      }
    }
  }

  window.LocalPreviewLibrary = LocalPreviewLibrary;
  window.LocalCardPreview = LocalCardPreview;
})();
