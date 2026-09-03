// Offline Zotero API simulation. No desktop or library access.
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const template = await fs.readFile(new URL('../skills/zotero-paper-notes/scripts/write_note.js', import.meta.url), 'utf8');
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
const job = {
  id: 'mock1', parentKey: 'PARENT01', noteKey: 'NOTETEST',
  expectedHTML: '<p>before</p>', html: '<h2>自选栏目</h2><p>after</p>{{FIG1}}',
  resultFile: '/result.json', images: [{marker: '{{FIG1}}', file: '/fig.jpg',
    mime: 'image/jpeg', width: 900, height: 600, caption: 'Fig.1 <original>',
    pdfKey: 'PDFTEST1', page: 3, sha256: 'synthetic'}]
};
function setup({changed=false, wrongParent=false, failImport=false, wrongPDF=false, editDuringImport=false}={}) {
  const files = new Map([['/job.json', JSON.stringify(job)], ['/fig.jpg', new Uint8Array([1,2,3])]]);
  let html = changed ? '<p>user edit</p>' : job.expectedHTML, imports=0, saves=0;
  const note = {id: 1, libraryID: 1, parentItemKey: wrongParent ? 'OTHERKEY' : job.parentKey,
    isNote: () => true, getNote: () => html, setNote: x => html=x, saveTx: async () => {saves++;}};
  const pdf = {isAttachment: () => true, parentItemKey: wrongPDF ? 'OTHERKEY' : job.parentKey,
    attachmentContentType: 'application/pdf'};
  const Zotero = {isWin: false, Libraries: {userLibraryID: 1},
    Items: {getByLibraryAndKey: (_,key) => key === job.noteKey ? note : pdf},
    Attachments: {importEmbeddedImage: async () => {
      imports++;
      if (failImport) throw Error('import failure');
      if (editDuringImport) html='<p>new user edit</p>';
      return {key: 'IMAGE001'};
    }}};
  const IOUtils = {
    readUTF8: async p => files.get(p),
    read: async p => {if (!files.has(p)) throw Error('missing file'); return files.get(p);},
    exists: async p => files.has(p), writeUTF8: async (p,x) => files.set(p,x)
  };
  const execute = () => new AsyncFunction('IOUtils','Zotero','Blob',
    template.replace('__JOB_FILE_JSON__', '"/job.json"'))(IOUtils, Zotero, Blob);
  return {execute, files, state: () => ({html, imports, saves})};
}
let test = setup();
await test.execute();
assert.equal(test.state().imports, 1);
assert.equal(test.state().saves, 1);
assert.match(test.state().html, /data-attachment-key="IMAGE001"/);
assert.match(test.state().html, /&lt;original&gt;/);
assert.match(test.state().html, /<h2>自选栏目<\/h2>/);
assert.match(test.state().html, /items\/PDFTEST1\?page=3/);
await test.execute();
assert.equal(test.state().imports, 1);
assert.equal(test.state().saves, 1);
for (const options of [{changed:true}, {wrongParent:true}, {wrongPDF:true}]) {
  test=setup(options);
  await assert.rejects(test.execute);
  assert.equal(test.state().imports, 0);
  assert.equal(test.state().saves, 0);
}
test=setup({failImport:true});
await assert.rejects(test.execute);
assert.equal(JSON.parse(test.files.get('/result.json')).stage, 'failed');
await assert.rejects(test.execute, /Earlier attempt/);
assert.equal(test.state().imports, 1);
assert.equal(test.state().saves, 0);
test=setup({editDuringImport:true});
await assert.rejects(test.execute, /Concurrent note edit/);
assert.equal(test.state().html, '<p>new user edit</p>');
assert.equal(test.state().saves, 0);
assert.equal(JSON.parse(test.files.get('/result.json')).images[0].key, 'IMAGE001');
console.log('Writer checks passed: save, source link, custom headings, retry, target guards and concurrent edits.');
