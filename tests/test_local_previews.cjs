// Exercise local matching and storage contracts without browser automation.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'local_previews.js'), 'utf8');
const records = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'motionsites_all_prompts.json'), 'utf8'));

function load(indexedDB) {
  const window = { indexedDB };
  const context = vm.createContext({ window, indexedDB, Blob, console });
  vm.runInContext(source, context);
  return window.LocalPreviewLibrary;
}

function media(name, relative) {
  const file = new Blob(['local test fixture'], { type: 'video/mp4' });
  file.name = name;
  file.webkitRelativePath = relative || '';
  return file;
}

function storageMock(shared = new Map(), failWrites = false) {
  return {
    open() {
      const request = {};
      queueMicrotask(() => {
        request.result = {
          close() {},
          transaction() {
            const transaction = {};
            transaction.objectStore = () => ({
              getAllKeys() {
                const request = {};
                queueMicrotask(() => { request.result = [...shared.keys()]; request.onsuccess(); });
                return request;
              },
              get(id) {
                const request = {};
                queueMicrotask(() => { request.result = shared.get(id); request.onsuccess(); });
                return request;
              },
              put(record) {
                queueMicrotask(() => {
                  if (failWrites) {
                    transaction.error = new Error('QuotaExceededError');
                    transaction.onabort();
                  } else {
                    shared.set(record.id, record);
                    transaction.oncomplete();
                  }
                });
              },
            });
            return transaction;
          },
        };
        request.onsuccess();
      });
      return request;
    },
  };
}

(async () => {
  let checks = 0;
  const Library = load(undefined);
  const library = new Library(records, {}, () => {});
  await library.init();
  assert.match(library.storageMessage, /无法保存缓存/); checks++;
  assert.equal(library.match(media('Interactive Discovery.mp4')), 'interactive-discovery'); checks++;
  assert.equal(library.match(media('projects-catalog.webm')), 'projects-catalog'); checks++;
  assert.equal(library.match(media('video.mp4', 'supplement-shop/video.mp4')), 'supplement-shop'); checks++;
  assert.equal(library.match(media('interactive-discovery.html')), null); checks++;
  assert.equal(library.match(media('unknown.mp4')), null); checks++;
  const collision = new Library([{id: 'portal', title: 'Portal Dashboard'}, {id: 'portal-hero', title: 'Portal'}], {}, () => {});
  assert.equal(collision.match(media('portal.mp4')), 'portal'); checks++;
  const report = await library.importFiles([media('Interactive Discovery.mp4'), media('unknown.mp4')]);
  assert.equal(report.imported, 1);
  assert.equal(report.saved, 0);
  assert.equal(report.sessionOnly, 1); checks++;
  assert.equal(library.count(), 1);
  assert.ok((await library.get('interactive-discovery')).blob instanceof Blob); checks++;
  const conflict = await library.importFiles([media('interactive-discovery.mp4'), media('Interactive Discovery.webm')]);
  assert.equal(conflict.imported, 0);
  assert.equal(conflict.duplicates[0], 'interactive-discovery'); checks++;
  assert.equal(await library.get('missing'), null); checks++;
  const bundled = new Library(records, {'interactive-discovery': {path: 'media/interactive-discovery-123.mp4'}}, () => {});
  assert.equal((await bundled.get('interactive-discovery')).url, 'media/interactive-discovery-123.mp4'); checks++;
  const hostile = new Library(records, {'interactive-discovery': {path: 'https://example.com/private.mp4'}}, () => {});
  assert.equal(await hostile.get('interactive-discovery'), null); checks++;
  const mixed = new Library(records, {
    'interactive-discovery': {path: 'media/interactive-discovery-123.png', kind: 'image', poster: 'media/interactive-discovery-123.png'},
    'projects-catalog': {path: 'media/projects-catalog-456.mp4', kind: 'video'},
  }, () => {});
  assert.equal((await mixed.get('interactive-discovery')).kind, 'image'); checks++;
  assert.equal(mixed.poster('interactive-discovery'), 'media/interactive-discovery-123.png'); checks++;
  assert.equal(mixed.countsByKind().image, 1);
  assert.equal(mixed.countsByKind().video, 1); checks++;
  await mixed.importFiles([media('interactive-discovery.mp4')]);
  assert.equal(mixed.countsByKind().image, 0);
  assert.equal(mixed.countsByKind().video, 2); checks++;

  const shared = new Map();
  const Persistent = load(storageMock(shared));
  const first = new Persistent(records, {}, () => {});
  await first.init();
  const saved = await first.importFiles([media('interactive-discovery.mp4')]);
  assert.equal(saved.saved, 1); checks++;
  const reopened = new Persistent(records, {}, () => {});
  await reopened.init();
  assert.equal(reopened.count(), 1);
  assert.ok((await reopened.get('interactive-discovery')).blob instanceof Blob); checks++;
  const Failing = load(storageMock(new Map(), true));
  const failing = new Failing(records, {}, () => {});
  await failing.init();
  const failed = await failing.importFiles([media('interactive-discovery.mp4')]);
  assert.equal(failed.saved, 0);
  assert.equal(failed.sessionOnly, 1);
  assert.equal(failed.errors.length, 1);
  assert.ok((await failing.get('interactive-discovery')).blob instanceof Blob); checks++;
  console.log(`${checks} local preview checks passed (storage mocked; no browser playback claim).`);
})().catch(error => { console.error(error); process.exitCode = 1; });
