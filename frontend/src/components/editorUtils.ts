// Insert plain text (e.g. a {{.Token}}) at the CKEditor cursor. Kept separate
// from RichEditor so importing it doesn't pull the heavy CKEditor bundle.
export function insertIntoEditor(editor: any, text: string) {
  if (!editor) return;
  editor.model.change((writer: any) => {
    editor.model.insertContent(writer.createText(text), editor.model.document.selection);
  });
  editor.editing.view.focus();
}
