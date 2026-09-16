-- Exercise LazyVim's registered BufWritePre path using unsaved buffer text.
local function run()
  local result = { cases = {} }
  local ok, err = xpcall(function()
    result.lazy_save_callbacks = #vim.api.nvim_get_autocmds({ event = "BufWritePre", group = "LazyFormat" })
    assert(result.lazy_save_callbacks > 0, "LazyVim save callback was not registered")
    local spec = vim.json.decode(table.concat(vim.fn.readfile(vim.env.FORMAT_EVAL_CASES), "\n"))
    local conform = require("conform")
    result.default_format_opts = conform.default_format_opts
    for _, case in ipairs(spec.cases) do
      vim.cmd.edit(vim.fn.fnameescape(case.path))
      local ft = vim.bo.filetype
      local input = vim.split(case.input:gsub("\n$", ""), "\n", { plain = true })
      vim.api.nvim_buf_set_lines(0, 0, -1, false, input)
      local sources = conform.list_formatters(0)
      local before_disk = table.concat(vim.fn.readfile(case.path), "\n") .. "\n"
      local started = vim.uv.hrtime()
      local wrote, write_error = pcall(vim.cmd, "silent write")
      local elapsed = (vim.uv.hrtime() - started) / 1e6
      local output = table.concat(vim.fn.readfile(case.path), "\n") .. "\n"
      if not case.invalid then
        assert(wrote, write_error)
        vim.cmd("silent write")
      end
      local second = table.concat(vim.fn.readfile(case.path), "\n") .. "\n"
      local row = {
        name = case.name,
        filetype = ft,
        sources = sources,
        save_ms = elapsed,
        output = output,
        equals_direct = output == case.expected,
        stable = output == second,
        save_ok = wrote,
        save_error = not wrote and tostring(write_error) or nil,
        invalid = case.invalid,
        input_preserved_in_buffer = table.concat(vim.api.nvim_buf_get_lines(0, 0, -1, false), "\n") .. "\n" == case.input,
        disk_unchanged = output == before_disk,
      }
      if case.benchmark and vim.env.FORMAT_EVAL_MODE == "dprint" then
        row.samples_ms = {}
        for i = 1, 105 do
          local prefix = case.prefix:gsub("INDEX", tostring(i))
          vim.api.nvim_buf_set_lines(0, 0, -1, false, vim.split((prefix .. case.input):gsub("\n$", ""), "\n", { plain = true }))
          started = vim.uv.hrtime()
          vim.cmd("silent write")
          elapsed = (vim.uv.hrtime() - started) / 1e6
          local saved = table.concat(vim.fn.readfile(case.path), "\n") .. "\n"
          assert(saved == prefix .. case.expected, "Benchmark save mismatch: " .. case.name)
          if i > 5 then
            table.insert(row.samples_ms, elapsed)
          end
        end
      end
      table.insert(result.cases, row)
    end
  end, debug.traceback)
  result.ok = ok
  result.error = not ok and err or nil
  local log = vim.fn.stdpath("state") .. "/conform.log"
  result.formatter_log = vim.fn.filereadable(log) == 1 and vim.fn.readfile(log) or {}
  vim.fn.writefile({ vim.json.encode(result) }, vim.env.FORMAT_EVAL_OUTPUT)
  vim.cmd(ok and "qa!" or "cquit 1")
end

vim.api.nvim_create_autocmd("VimEnter", {
  once = true,
  callback = function()
    -- lazy.nvim defers VeryLazy until UIEnter; headless startup otherwise skips it.
    vim.api.nvim_exec_autocmds("UIEnter", {})
    vim.defer_fn(run, 1000)
  end,
})
