import { CKEditor } from "@ckeditor/ckeditor5-react";
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore -- the predefined build ships without full TS types
import ClassicEditor from "@ckeditor/ckeditor5-build-classic";

// Upload adapter: an uploaded/pasted image becomes a data: URI, so images work
// with no server-side upload endpoint. (Fine for simulations.)
class Base64Adapter {
  loader: any;
  constructor(loader: any) {
    this.loader = loader;
  }
  upload() {
    return this.loader.file.then(
      (file: File) =>
        new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve({ default: reader.result });
          reader.onerror = reject;
          reader.readAsDataURL(file);
        }),
    );
  }
  abort() {}
}

function Base64Plugin(editor: any) {
  editor.plugins.get("FileRepository").createUploadAdapter = (loader: any) => new Base64Adapter(loader);
}

export default function RichEditor({
  value,
  onChange,
  onReady,
}: {
  value: string;
  onChange: (html: string) => void;
  onReady?: (editor: any) => void;
}) {
  return (
    <div className="rich-editor">
      <CKEditor
        editor={ClassicEditor}
        data={value}
        config={{
          extraPlugins: [Base64Plugin],
          toolbar: [
            "heading", "|",
            "bold", "italic", "underline", "link", "|",
            "bulletedList", "numberedList", "blockQuote", "|",
            "insertTable", "imageUpload", "mediaEmbed", "|",
            "alignment", "outdent", "indent", "|",
            "undo", "redo",
          ],
        }}
        onReady={(editor: any) => onReady?.(editor)}
        onChange={(_evt: unknown, editor: any) => onChange(editor.getData())}
      />
    </div>
  );
}
