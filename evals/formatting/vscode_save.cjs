// Loaded by VS Code's extension-host test runner. save() invokes save participants.
const vscode = require("vscode");
const fs = require("node:fs");
const { performance } = require("node:perf_hooks");

exports.run = async function () {
  const spec = JSON.parse(fs.readFileSync(process.env.FORMAT_EVAL_CASES, "utf8"));
  const result = { cases: [], extensions: {} };
  const mode = process.env.FORMAT_EVAL_MODE;
  try {
    for (const id of ["dprint.dprint", "esbenp.prettier-vscode", "yzhang.markdown-all-in-one", "dbaeumer.vscode-eslint", "stylelint.vscode-stylelint"]) {
      const extension = vscode.extensions.getExtension(id);
      if (extension) {
        await extension.activate();
        result.extensions[id] = extension.packageJSON.version;
      }
    }
    result.workspace_folders = (vscode.workspace.workspaceFolders || []).map(folder => folder.uri.fsPath);
    result.dprint_restarted = await vscode.commands.executeCommand("dprint.restart");
    // Wait for registration after activation; configuration is frozen before launch.
    await new Promise(resolve => setTimeout(resolve, 1000));
    for (const test of spec.cases) {
      const uri = vscode.Uri.file(test.path);
      const document = await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(document);
      const language = document.languageId;
      const replace = async text => {
        const edit = new vscode.WorkspaceEdit();
        edit.replace(uri, new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length)), text);
        if (!await vscode.workspace.applyEdit(edit)) throw new Error("Edit failed");
      };
      await replace(test.input);
      const started = performance.now();
      const saved = await document.save();
      const elapsed = performance.now() - started;
      const output = fs.readFileSync(test.path, "utf8");
      const bufferAfterFirstSave = document.getText();
      // A canceled save leaves old disk content; preserve the unsaved buffer.
      await replace(document.getText());
      const secondSaved = await document.save();
      const secondOutput = fs.readFileSync(test.path, "utf8");
      const row = {
        name: test.name, language, saved, save_ms: elapsed, output,
        equals_direct: output === test.expected,
        stable: saved && secondSaved && output === secondOutput,
        second_saved: secondSaved,
        second_output: secondOutput,
        buffer_after_first_save: bufferAfterFirstSave,
        second_equals_direct: secondOutput === test.expected,
        formatter: vscode.workspace.getConfiguration("editor", document).get("defaultFormatter"),
        format_on_save: vscode.workspace.getConfiguration("editor", document).get("formatOnSave"),
      };
      result.cases.push(row);
      if (test.benchmark && mode === "dprint") {
        row.samples_ms = [];
        for (let i = 1; i <= 105; i++) {
          const prefix = test.prefix.replace("INDEX", String(i));
          await replace(prefix + test.input);
          const start = performance.now();
          await document.save();
          const ms = performance.now() - start;
          if (fs.readFileSync(test.path, "utf8") !== prefix + test.expected) throw new Error(`Benchmark mismatch: ${test.name}`);
          if (i > 5) row.samples_ms.push(ms);
        }
      }
    }
    if (mode === "dprint" && spec.cache_case) {
      const test = spec.cache_case;
      const uri = vscode.Uri.file(test.path);
      const document = await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(document);
      const outputs = [];
      for (const singleQuote of [false, true]) {
        fs.writeFileSync(test.config_path, JSON.stringify({ singleQuote }));
        const edit = new vscode.WorkspaceEdit();
        edit.replace(uri, new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length)), test.input);
        await vscode.workspace.applyEdit(edit);
        const saved = await document.save();
        outputs.push({ saved, text: fs.readFileSync(test.path, "utf8") });
      }
      result.external_config_refresh = {
        outputs,
        pass: outputs[0].saved && outputs[1].saved && outputs[0].text.includes('"hello"') && outputs[1].text.includes("'hello'"),
      };
    }
    result.ok = true;
  } catch (error) {
    result.ok = false;
    result.error = String(error.stack || error);
    throw error;
  } finally {
    fs.writeFileSync(process.env.FORMAT_EVAL_OUTPUT, JSON.stringify(result, null, 2) + "\n");
  }
};
