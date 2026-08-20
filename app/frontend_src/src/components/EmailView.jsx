import React, { useState, useCallback } from "react";
import { Mail, Send, Eye, FileSpreadsheet, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { cx } from "./DashboardUI";

export function EmailView({ config, notify, t }) {
  const [smtpUser, setSmtpUser] = useState(config?.email_smtp_user || "");
  const [smtpPassword, setSmtpPassword] = useState(config?.email_smtp_password || "");
  const [senderName, setSenderName] = useState(config?.email_sender_name || "");
  const [excelPath, setExcelPath] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [delaySeconds, setDelaySeconds] = useState(2);
  const [testing, setTesting] = useState(false);
  const [sending, setSending] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [sendResult, setSendResult] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [previewing, setPreviewing] = useState(false);

  const handleTestConnection = useCallback(async () => {
    if (!smtpUser || !smtpPassword) {
      notify?.(t("emailFillCredentials") || "请填写邮箱和授权码");
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch("/email/test-connection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ smtp_user: smtpUser, smtp_password: smtpPassword, sender_name: senderName }),
      });
      const data = await res.json();
      setTestResult(data);
      if (data.status === "success") {
        notify?.(t("emailConnectionOk") || "SMTP连接成功");
      } else {
        notify?.(data.message || t("emailConnectionFail") || "SMTP连接失败");
      }
    } catch (err) {
      setTestResult({ status: "error", message: err.message });
      notify?.(err.message);
    } finally {
      setTesting(false);
    }
  }, [smtpUser, smtpPassword, senderName, notify, t]);

  const handlePreview = useCallback(async () => {
    if (!excelPath || !subject || !body) {
      notify?.(t("emailFillAll") || "请填写Excel路径、主题和正文");
      return;
    }
    setPreviewing(true);
    setPreviewData(null);
    try {
      const res = await fetch("/email/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          smtp_user: smtpUser,
          smtp_password: smtpPassword,
          sender_name: senderName,
          excel_path: excelPath,
          subject,
          body,
          delay_seconds: delaySeconds,
          dry_run: true,
        }),
      });
      const data = await res.json();
      setPreviewData(data);
    } catch (err) {
      setPreviewData({ status: "error", message: err.message });
      notify?.(err.message);
    } finally {
      setPreviewing(false);
    }
  }, [smtpUser, smtpPassword, senderName, excelPath, subject, body, delaySeconds, notify, t]);

  const handleSend = useCallback(async () => {
    if (!smtpUser || !smtpPassword || !excelPath || !subject || !body) {
      notify?.(t("emailFillAll") || "请填写所有字段");
      return;
    }
    setSending(true);
    setSendResult(null);
    try {
      const res = await fetch("/email/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          smtp_user: smtpUser,
          smtp_password: smtpPassword,
          sender_name: senderName,
          excel_path: excelPath,
          subject,
          body,
          delay_seconds: delaySeconds,
          dry_run: false,
        }),
      });
      const data = await res.json();
      setSendResult(data);
      if (data.status === "success" || data.success_count > 0) {
        notify?.(t("emailSendOk") || `发送成功：${data.success_count}/${data.total}封`);
      } else {
        notify?.(data.message || t("emailSendFail") || "发送失败");
      }
    } catch (err) {
      setSendResult({ status: "error", message: err.message });
      notify?.(err.message);
    } finally {
      setSending(false);
    }
  }, [smtpUser, smtpPassword, senderName, excelPath, subject, body, delaySeconds, notify, t]);

  const inputClass = "w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100";
  const labelClass = "mb-1 block text-xs font-medium text-slate-500";

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
      {/* 邮箱配置 */}
      <section className="soft-section rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/50">
        <div className="mb-4 flex items-center gap-2">
          <Mail size={18} className="text-indigo-500" />
          <h2 className="text-sm font-bold text-slate-900">{t("emailConfigTitle") || "邮箱配置"}</h2>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className={labelClass}>{t("emailSmtpUser") || "邮箱地址"}</label>
            <input className={inputClass} type="text" value={smtpUser} onChange={(e) => setSmtpUser(e.target.value)} placeholder="your@qq.com" />
          </div>
          <div>
            <label className={labelClass}>{t("emailSmtpPassword") || "SMTP授权码"}</label>
            <input className={inputClass} type="password" value={smtpPassword} onChange={(e) => setSmtpPassword(e.target.value)} placeholder="授权码（非登录密码）" />
          </div>
          <div>
            <label className={labelClass}>{t("emailSenderName") || "发件人显示名"}</label>
            <input className={inputClass} type="text" value={senderName} onChange={(e) => setSenderName(e.target.value)} placeholder="Cindy" />
          </div>
          <div className="flex items-end">
            <button
              className={cx("flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition", testing ? "bg-slate-100 text-slate-400" : "bg-indigo-500 text-white hover:bg-indigo-600")}
              onClick={handleTestConnection}
              disabled={testing}
              type="button"
            >
              {testing ? <Loader2 size={16} className="animate-spin" /> : <Mail size={16} />}
              {testing ? (t("emailTesting") || "测试中...") : (t("emailTestConnection") || "测试连接")}
            </button>
          </div>
        </div>
        {testResult && (
          <div className={cx("mt-3 flex items-center gap-2 rounded-lg px-3 py-2 text-xs", testResult.status === "success" ? "bg-green-50 text-green-600" : "bg-red-50 text-red-600")}>
            {testResult.status === "success" ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
            <span>{testResult.status === "success" ? `✓ ${testResult.smtp_host}:${testResult.smtp_port} SSL (${testResult.elapsed_seconds}s)` : testResult.message}</span>
          </div>
        )}
      </section>

      {/* 邮件内容 */}
      <section className="soft-section rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/50">
        <div className="mb-4 flex items-center gap-2">
          <FileSpreadsheet size={18} className="text-indigo-500" />
          <h2 className="text-sm font-bold text-slate-900">{t("emailContentTitle") || "邮件内容"}</h2>
        </div>
        <div className="space-y-3">
          <div>
            <label className={labelClass}>{t("emailExcelPath") || "Excel文件路径"}</label>
            <input className={inputClass} type="text" value={excelPath} onChange={(e) => setExcelPath(e.target.value)} placeholder="/Users/xxx/Desktop/contacts.xlsx" />
            <p className="mt-1 text-[11px] text-slate-400">{t("emailExcelHint") || "Excel须包含「姓名」和「邮箱」列，可含其他列作为模板变量"}</p>
          </div>
          <div>
            <label className={labelClass}>{t("emailSubject") || "邮件主题"}</label>
            <input className={inputClass} type="text" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="尊敬的{{姓氏}}老师，..." />
          </div>
          <div>
            <label className={labelClass}>{t("emailBody") || "邮件正文"}</label>
            <textarea className={cx(inputClass, "h-48 resize-y")} value={body} onChange={(e) => setBody(e.target.value)} placeholder={"尊敬的{{姓氏}}老师，您好：\n\n..."} />
            <p className="mt-1 text-[11px] text-slate-400">{t("emailTemplateHint") || "支持变量：{{姓氏}} {{姓名}} {{名字}} {{邮箱}} 以及Excel中的任意列名"}</p>
          </div>
          <div className="flex items-center gap-3">
            <label className={cx(labelClass, "mb-0 whitespace-nowrap")}>{t("emailDelay") || "发送间隔(秒)"}</label>
            <input className={cx(inputClass, "w-20")} type="number" min="0" step="0.5" value={delaySeconds} onChange={(e) => setDelaySeconds(parseFloat(e.target.value) || 1)} />
          </div>
        </div>
      </section>

      {/* 操作按钮 */}
      <div className="flex flex-wrap gap-3">
        <button
          className={cx("flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition", previewing ? "bg-slate-100 text-slate-400" : "bg-slate-100 text-slate-700 hover:bg-slate-200")}
          onClick={handlePreview}
          disabled={previewing}
          type="button"
        >
          {previewing ? <Loader2 size={16} className="animate-spin" /> : <Eye size={16} />}
          {previewing ? (t("emailPreviewing") || "预览中...") : (t("emailPreview") || "演练预览")}
        </button>
        <button
          className={cx("flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition", sending ? "bg-slate-100 text-slate-400" : "bg-indigo-500 text-white hover:bg-indigo-600")}
          onClick={handleSend}
          disabled={sending}
          type="button"
        >
          {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          {sending ? (t("emailSending") || "发送中...") : (t("emailSend") || "批量发送")}
        </button>
      </div>

      {/* 预览结果 */}
      {previewData && (
        <section className="soft-section rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/50">
          <h3 className="mb-3 text-sm font-bold text-slate-900">{t("emailPreviewResult") || "预览结果"}</h3>
          {previewData.status === "success" && previewData.results ? (
            <div className="space-y-2">
              {previewData.results.map((r, i) => (
                <div key={i} className="flex items-start gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs">
                  <span className="font-mono text-slate-400">[{r.index}]</span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-slate-700">{r.name} &lt;{r.email}&gt;</div>
                    <div className="truncate text-slate-500">{r.subject}</div>
                  </div>
                  <span className={cx("whitespace-nowrap", r.status === "success" ? "text-green-500" : "text-red-500")}>
                    {r.status === "success" ? "✓" : "✗"} {r.message}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-red-500">{previewData.message || JSON.stringify(previewData)}</div>
          )}
        </section>
      )}

      {/* 发送结果 */}
      {sendResult && (
        <section className="soft-section rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/50">
          <h3 className="mb-3 text-sm font-bold text-slate-900">{t("emailSendResult") || "发送结果"}</h3>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-slate-50 px-3 py-2 text-center">
              <div className="text-lg font-bold text-slate-700">{sendResult.total || 0}</div>
              <div className="text-[11px] text-slate-400">{t("emailTotal") || "总计"}</div>
            </div>
            <div className="rounded-lg bg-green-50 px-3 py-2 text-center">
              <div className="text-lg font-bold text-green-600">{sendResult.success_count || 0}</div>
              <div className="text-[11px] text-green-400">{t("emailSuccess") || "成功"}</div>
            </div>
            <div className="rounded-lg bg-red-50 px-3 py-2 text-center">
              <div className="text-lg font-bold text-red-600">{sendResult.failed_count || 0}</div>
              <div className="text-[11px] text-red-400">{t("emailFailed") || "失败"}</div>
            </div>
          </div>
          {sendResult.results && sendResult.failed_count > 0 && (
            <div className="mt-3 space-y-1">
              {sendResult.results.filter((r) => r.status !== "success").map((r, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-red-500">
                  <AlertCircle size={12} />
                  <span>[{r.index}] {r.email}: {r.message}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
