// Template: note_job.py supplies a concrete, quoted job-file path.
var jobFile = __JOB_FILE_JSON__;
var nativePath = p => Zotero.isWin ? p.replaceAll('/', '\\') : p;
var job = JSON.parse(await IOUtils.readUTF8(nativePath(jobFile)));
var resultFile = nativePath(job.resultFile);
if (await IOUtils.exists(resultFile)) {
  var previous = JSON.parse(await IOUtils.readUTF8(resultFile));
  if (previous.id !== job.id) throw new Error('Result belongs to a different job');
  if (previous.stage === 'complete') return JSON.stringify(previous);
  throw new Error('Earlier attempt was incomplete. Inspect journal and library; do not rerun blindly.');
}
var note = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, job.noteKey);
if (!note || !note.isNote() || note.parentItemKey !== job.parentKey) throw new Error('Wrong target note');
if (note.getNote() !== job.expectedHTML) throw new Error('Note changed since snapshot; re-read and merge');
var escapeHTML = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
var bytes = [];
for (var image of job.images) {
  if (job.html.split(image.marker).length !== 2) throw new Error('Image marker missing or duplicated');
  var pdf = Zotero.Items.getByLibraryAndKey(note.libraryID, image.pdfKey);
  if (!pdf || !pdf.isAttachment() || pdf.parentItemKey !== job.parentKey || pdf.attachmentContentType !== 'application/pdf') {
    throw new Error('Figure source is not a PDF belonging to this article');
  }
  bytes.push(await IOUtils.read(nativePath(image.file)));
}
// Validate all source files before the first library mutation.
var journal = {id:job.id, noteKey:job.noteKey, parentKey:job.parentKey, stage:'started', images:[]};
var record = async () => IOUtils.writeUTF8(resultFile, JSON.stringify(journal));
await record();
try {
  var html = job.html;
  for (var i = 0; i < job.images.length; i++) {
    var image = job.images[i];
    var attachment = await Zotero.Attachments.importEmbeddedImage({
      blob:new Blob([bytes[i]], {type:image.mime}), parentItemID:note.id
    });
    journal.images.push({key:attachment.key, marker:image.marker, sha256:image.sha256});
    await record();
    var block = '<p><strong>' + escapeHTML(image.caption) + '</strong></p>'
      + '<p><img data-attachment-key="' + attachment.key + '" width="' + image.width
      + '" height="' + image.height + '" alt="' + escapeHTML(image.caption) + '"></p>'
      + '<p><a href="zotero://open-pdf/library/items/' + image.pdfKey + '?page=' + image.page
      + '">原文 PDF 第 ' + image.page + ' 页及图注</a></p>';
    html = html.replace(image.marker, () => block);
  }
  if (note.getNote() !== job.expectedHTML) throw new Error('Concurrent note edit; imported images recorded, note unchanged');
  journal.html = html;
  journal.stage = 'saving';
  await record();
  note.setNote(html);
  await note.saveTx();
  journal.stage = 'complete';
  journal.html = note.getNote();
  await record();
  return JSON.stringify({saved:true, note:job.noteKey, images:journal.images});
}
catch (error) {
  journal.stage = 'failed';
  journal.error = String(error);
  await record();
  throw error;
}
