import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  ArrowLeft,
  Building2,
  CheckCircle2,
  Clock3,
  FileSearch,
  FileText,
  LayoutDashboard,
  LogOut,
  ReceiptText,
  Save,
  Search,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import {
  deleteInvoice,
  fileUrl,
  getInvoice,
  listInvoices,
  updateInvoice,
  uploadInvoice,
} from "./api";
import { getUserProfile, initAuth, logout, refreshToken } from "./auth";
import "./styles.css";

const emptyInvoice = {
  invoice_number: "",
  invoice_date: "",
  seller: { name: "", address: "", vat_pan_number: "" },
  buyer: { name: "", address: "", vat_pan_number: "" },
  items: [],
  subtotal: "",
  discount: "",
  vat_amount: "",
  total_amount: "",
  currency: "",
  remarks: "",
  status: "completed",
};
const emptyItem = { description: "", quantity: "", rate: "", amount: "" };
const filterOptions = [
  { value: "all", label: "All" },
  { value: "needs_review", label: "Need review" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];

function normalizeInvoice(invoice) {
  return {
    ...emptyInvoice,
    ...invoice,
    invoice_number: invoice.invoice_number || "",
    invoice_date: invoice.invoice_date || "",
    seller: {
      name: invoice.seller?.name || invoice.seller_name || "",
      address: invoice.seller?.address || "",
      vat_pan_number: invoice.seller?.vat_pan_number || "",
    },
    buyer: {
      name: invoice.buyer?.name || invoice.buyer_name || "",
      address: invoice.buyer?.address || "",
      vat_pan_number: invoice.buyer?.vat_pan_number || "",
    },
    items: invoice.items?.length ? invoice.items : [emptyItem],
    subtotal: invoice.subtotal || "",
    discount: invoice.discount || "",
    vat_amount: invoice.vat_amount || "",
    total_amount: invoice.total_amount || "",
    currency: invoice.currency || "",
    remarks: invoice.remarks || "",
  };
}

function cleanNumber(value) {
  return value === "" || value === null ? null : String(value);
}

function asNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatMoney(value, currency = "NPR") {
  if (value === null || value === undefined || value === "") return "Pending";
  return `${currency || "NPR"} ${asNumber(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatDate(value) {
  if (!value) return "Date pending";
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function statusLabel(status) {
  if (!status) return "Unknown";
  if (status === "needs_review") return "Need review";
  return status.replace("_", " ");
}

function toPayload(form) {
  return {
    invoice_number: form.invoice_number || null,
    invoice_date: form.invoice_date || null,
    seller: {
      name: form.seller.name || null,
      address: form.seller.address || null,
      vat_pan_number: form.seller.vat_pan_number || null,
    },
    buyer: {
      name: form.buyer.name || null,
      address: form.buyer.address || null,
      vat_pan_number: form.buyer.vat_pan_number || null,
    },
    items: form.items.map((item) => ({
      description: item.description || null,
      quantity: cleanNumber(item.quantity),
      rate: cleanNumber(item.rate),
      amount: cleanNumber(item.amount),
    })),
    subtotal: cleanNumber(form.subtotal),
    discount: cleanNumber(form.discount),
    vat_amount: cleanNumber(form.vat_amount),
    total_amount: cleanNumber(form.total_amount),
    currency: form.currency || null,
    remarks: form.remarks || null,
    status: form.status || "completed",
  };
}

function StatusBadge({ status }) {
  return (
    <span className={`status status-${status}`}>
      {statusLabel(status)}
    </span>
  );
}

function Field({ label, value, onChange, type = "text" }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type={type}
        value={value || ""}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function App() {
  const fileInputRef = useRef(null);
  const [authReady, setAuthReady] = useState(false);
  const [profile, setProfile] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [selected, setSelected] = useState(null);
  const [page, setPage] = useState("hub");
  const [form, setForm] = useState(emptyInvoice);
  const [query, setQuery] = useState("");
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [busy, setBusy] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [pendingUploadName, setPendingUploadName] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    initAuth()
      .then(() => {
        setProfile(getUserProfile());
        setAuthReady(true);
      })
      .catch((error) => setMessage(error.message));
  }, []);

  useEffect(() => {
    if (!authReady) return undefined;
    const intervalId = window.setInterval(() => {
      refreshToken().catch(() =>
        setMessage("Session refresh failed. Please sign in again."),
      );
    }, 30000);
    return () => window.clearInterval(intervalId);
  }, [authReady]);

  async function refreshList(nextSelectedId = selectedId) {
    await refreshToken();
    const rows = await listInvoices();
    setInvoices(rows);
    if (nextSelectedId) {
      setSelectedId(nextSelectedId);
      return rows;
    }
    if (rows.length && !rows.some((invoice) => invoice.id === selectedId)) {
      setSelectedId(rows[0].id);
    }
    if (!rows.length) {
      setSelectedId(null);
    }
    return rows;
  }

  useEffect(() => {
    if (!authReady) return;
    refreshList().catch((error) => setMessage(error.message));
  }, [authReady]);

  useEffect(() => {
    if (!selectedId) {
      setSelected(null);
      setForm(emptyInvoice);
      return;
    }
    getInvoice(selectedId)
      .then((invoice) => {
        setSelected(invoice);
        setForm(normalizeInvoice(invoice));
      })
      .catch((error) => setMessage(error.message));
  }, [selectedId]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return invoices.filter((invoice) => {
      const matchesStatus =
        statusFilter === "all" ||
        invoice.status === statusFilter ||
        (statusFilter === "processing" &&
          (invoice.status === "processing" || invoice.status === "uploaded"));
      if (!matchesStatus) return false;
      if (!needle) return true;
      return [
        invoice.invoice_number,
        invoice.seller_name,
        invoice.buyer_name,
        statusLabel(invoice.status),
        invoice.file_name,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle));
    });
  }, [invoices, query, statusFilter]);

  const summary = useMemo(() => {
    const completed = invoices.filter(
      (invoice) => invoice.status === "completed",
    ).length;
    const needsReview = invoices.filter(
      (invoice) => invoice.status === "needs_review",
    ).length;
    return { completed, needsReview };
  }, [invoices]);

  function filterCount(filterValue) {
    if (filterValue === "all") return invoices.length;
    return invoices.filter((invoice) => invoice.status === filterValue).length;
  }

  async function uploadSelectedFile(file) {
    if (!file) return;
    setBusy(true);
    setPage("review");
    setSelectedId(null);
    setSelected(null);
    setForm(emptyInvoice);
    setPendingUploadName(file.name);
    setMessage("Uploading and extracting invoice...");
    try {
      await refreshToken();
      const invoice = await uploadInvoice(file);
      await refreshList(invoice.id);
      setSelectedId(invoice.id);
      setMessage(
        "Invoice uploaded. Review the extracted fields, then mark it reviewed when everything looks correct.",
      );
    } catch (error) {
      setMessage(error.message);
    } finally {
      setPendingUploadName("");
      setBusy(false);
    }
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    await uploadSelectedFile(file);
    event.target.value = "";
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragActive(false);
    uploadSelectedFile(event.dataTransfer.files?.[0]);
  }

  function openInvoice(invoiceId) {
    setSelectedId(invoiceId);
    setPage("review");
  }

  function applySearch() {
    setQuery(searchText);
  }

  async function handleSave() {
    if (!selected) return;
    setBusy(true);
    try {
      await refreshToken();
      const updated = await updateInvoice(selected.id, toPayload(form));
      setSelected(updated);
      setForm(normalizeInvoice(updated));
      await refreshList(updated.id);
      setMessage("Invoice saved successfully. Returning to dashboard...");
      window.setTimeout(() => {
        setPage("hub");
        setMessage("");
      }, 900);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleMarkReviewed() {
    if (!selected) return;
    if (!hasReviewBasics) {
      setMessage("Please fill invoice number, date, seller, buyer, and total before marking reviewed.");
      return;
    }
    setBusy(true);
    try {
      await refreshToken();
      const updated = await updateInvoice(
        selected.id,
        toPayload({ ...form, status: "completed" }),
      );
      setSelected(updated);
      setForm(normalizeInvoice(updated));
      await refreshList(updated.id);
      setMessage("Invoice reviewed and saved to the library.");
      window.setTimeout(() => {
        setPage("hub");
        setMessage("");
      }, 900);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!selected) return;
    setBusy(true);
    try {
      await refreshToken();
      await deleteInvoice(selected.id);
      setSelected(null);
      setSelectedId(null);
      setForm(emptyInvoice);
      await refreshList(null);
      setSelectedId(null);
      setPage("hub");
      setMessage("Invoice deleted.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  function setPartyField(party, field, value) {
    setForm((current) => ({
      ...current,
      [party]: { ...current[party], [field]: value },
    }));
  }

  function setItemField(index, field, value) {
    setForm((current) => ({
      ...current,
      items: current.items.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [field]: value } : item,
      ),
    }));
  }

  function addItem() {
    setForm((current) => ({
      ...current,
      items: [...current.items, emptyItem],
    }));
  }

  function removeItem(index) {
    setForm((current) => ({
      ...current,
      items: current.items.filter((_, itemIndex) => itemIndex !== index),
    }));
  }

  const selectedFileSrc = selected?.file_url ? fileUrl(selected.file_url) : "";
  const isReviewed = (form.status || selected?.status) === "completed";
  const hasReviewBasics = Boolean(
    form.invoice_number &&
      form.invoice_date &&
      form.seller.name &&
      form.buyer.name &&
      form.total_amount,
  );
  const canMarkReviewed =
    Boolean(selected) && !isReviewed && selected?.status !== "failed";

  return (
    <main
      className={
        page === "hub" ? "app-shell hub-page" : "app-shell review-page"
      }
    >
      <input
        className="hidden-input"
        disabled={busy}
        ref={fileInputRef}
        type="file"
        accept=".pdf,image/png,image/jpeg,image/webp"
        onChange={handleUpload}
      />

      <header className="app-header">
        <button className="brand-button" onClick={() => setPage("hub")}>
          <ReceiptText size={26} />
          <span>
            <strong>Invoice Recognition</strong>
          </span>
        </button>

        <div className="header-tools">
          {page === "hub" && (
            <div className="search header-search">
              <input
                value={searchText}
                onChange={(event) => setSearchText(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    applySearch();
                  }
                }}
                placeholder="Search invoices"
              />
              <button className="search-action" onClick={applySearch} title="Search invoices">
                <Search size={16} />
              </button>
            </div>
          )}

          {profile && (
            <div className="user-strip">
              <div>
                <span>{profile.name}</span>
                <p>{profile.email}</p>
              </div>
              <button className="icon-button" onClick={logout} title="Sign out">
                <LogOut size={17} />
              </button>
            </div>
          )}
        </div>
      </header>

      {page === "hub" ? (
        <section className="hub">
          <div className="hub-hero">
            <div className="hero-copy">
              <p className="eyebrow">Smart invoice workspace</p>
              <h1>Upload an invoice to begin</h1>
              <p>
                Drop a bill, receipt, or supplier invoice here. The app extracts
                the fields, then opens a review page where you can correct
                totals, parties, and line items.
              </p>
              <div className="hero-actions">
                <button
                  className="primary-action"
                  disabled={busy}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload size={18} />
                  {busy ? "Reading invoice..." : "Choose invoice"}
                </button>
                {!!invoices.length && (
                  <button
                    className="secondary-action"
                    onClick={() => openInvoice(invoices[0].id)}
                  >
                    <FileSearch size={18} />
                    Open latest
                  </button>
                )}
              </div>
            </div>

            <button
              className={`drop-zone ${dragActive ? "drag-active" : ""}`}
              disabled={busy}
              onClick={() => fileInputRef.current?.click()}
              onDragEnter={(event) => {
                event.preventDefault();
                setDragActive(true);
              }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setDragActive(false)}
              onDrop={handleDrop}
            >
              <span className="drop-icon">
                <Sparkles size={30} />
              </span>
              <strong>
                {dragActive ? "Release to upload" : "Drag invoice here"}
              </strong>
              <small>PDF, JPG, PNG, or WEBP</small>
              <span className="scan-line" />
            </button>
          </div>

          {message && <div className="notice">{message}</div>}

          <section className="metrics-row">
            <div>
              <LayoutDashboard size={18} />
              <span>{invoices.length}</span>
              <p>Total invoices</p>
            </div>
            <div>
              <CheckCircle2 size={18} />
              <span>{summary.completed}</span>
              <p>Completed</p>
            </div>
            <div>
              <AlertTriangle size={18} />
              <span>{summary.needsReview}</span>
              <p>Need review</p>
            </div>
          </section>

          <section className="invoice-board">
            <div className="board-toolbar">
              <div>
                <p className="eyebrow">Invoice library</p>
                <h2>Click any invoice to review</h2>
              </div>
              <div className="filter-tabs" aria-label="Filter invoices">
                {filterOptions.map((option) => (
                  <button
                    className={statusFilter === option.value ? "active" : ""}
                    key={option.value}
                    onClick={() => setStatusFilter(option.value)}
                  >
                    {option.label}
                    <span>{filterCount(option.value)}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="invoice-grid">
              {filtered.map((invoice) => (
                <button
                  className={`invoice-card invoice-card-${invoice.status}`}
                  key={invoice.id}
                  onClick={() => openInvoice(invoice.id)}
                >
                  <span className="card-icon">
                    <FileText size={22} />
                  </span>
                  <span className="row-topline">
                    <span className="row-title">
                      {invoice.invoice_number || invoice.file_name}
                    </span>
                    <StatusBadge status={invoice.status} />
                  </span>
                  <span className="row-meta">
                    <Building2 size={14} />
                    {invoice.seller_name || "Seller pending"}
                  </span>
                  <span className="row-footer">
                    <span>{formatDate(invoice.invoice_date)}</span>
                    <strong>
                      {formatMoney(invoice.total_amount, invoice.currency)}
                    </strong>
                  </span>
                </button>
              ))}
              {!filtered.length && (
                <div className="blank-state compact">
                  <FileText size={38} />
                  <h3>No invoices found</h3>
                  <p>Upload your first invoice, clear search, or switch filters.</p>
                </div>
              )}
            </div>
          </section>
        </section>
      ) : (
        <section className="workspace">
          <header className="topbar">
            <div>
              <button className="back-button" onClick={() => setPage("hub")}>
                <ArrowLeft size={17} />
                Dashboard
              </button>
              <p className="eyebrow">Review workspace</p>
              <h2>
                {selected
                  ? selected.file_name
                  : pendingUploadName || "Upload an invoice to begin"}
              </h2>
            </div>
            {selected && (
              <div className="actions">
                <a
                  className="icon-link"
                  href={selectedFileSrc}
                  target="_blank"
                  rel="noreferrer"
                >
                  <FileText size={18} />
                  Original
                </a>
                <button
                  className="icon-button danger"
                  disabled={busy}
                  onClick={handleDelete}
                  title="Delete"
                >
                  <Trash2 size={18} />
                </button>
                <button
                  className="primary-action"
                  disabled={busy}
                  onClick={handleSave}
                >
                  <Save size={18} />
                  Save
                </button>
                {canMarkReviewed && (
                  <button
                    className="reviewed-action"
                    disabled={busy}
                    onClick={handleMarkReviewed}
                  >
                    <CheckCircle2 size={18} />
                    Reviewed
                  </button>
                )}
              </div>
            )}
          </header>

          {message && <div className="notice">{message}</div>}

          {!selected ? (
            <div className="blank-state">
              {busy && pendingUploadName ? (
                <>
                  <Upload className="spin-icon" size={42} />
                  <h3>Reading {pendingUploadName}</h3>
                  <p>
                    Extracting invoice fields now. The review form will appear
                    as soon as the new invoice is ready.
                  </p>
                </>
              ) : (
                <>
                  <FileText size={42} />
                  <h3>Upload an invoice to begin</h3>
                  <p>
                    Choose a PDF, JPG, PNG, or WEBP invoice and the review page
                    will open automatically.
                  </p>
                  <button
                    className="primary-action"
                    disabled={busy}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Upload size={18} />
                    Choose invoice
                  </button>
                </>
              )}
            </div>
          ) : (
            <div className="review-layout">
              <aside className="document-pane">
                <div className="document-toolbar">
                  <div>
                    <p className="eyebrow">Source document</p>
                    <strong>{selected.file_name}</strong>
                  </div>
                  <StatusBadge status={selected.status} />
                </div>
                <div className="document-preview">
                  {selected.file_name?.toLowerCase().endsWith(".pdf") ? (
                    <iframe src={selectedFileSrc} title="Invoice preview" />
                  ) : (
                    <img src={selectedFileSrc} alt="Invoice preview" />
                  )}
                </div>
              </aside>

              <div className="detail-grid">
                {canMarkReviewed && (
                  <section className="review-callout">
                    <div>
                      <p className="eyebrow">Review required</p>
                      <h3>
                        Check the extracted fields before adding this invoice to
                        the library.
                      </h3>
                    </div>
                    <button
                      className="reviewed-action"
                      disabled={busy}
                      onClick={handleMarkReviewed}
                    >
                      <CheckCircle2 size={18} />
                      Reviewed
                    </button>
                  </section>
                )}

                <section className="review-summary">
                  <div>
                    <p className="eyebrow">Extracted total</p>
                    <h3>{formatMoney(form.total_amount, form.currency)}</h3>
                  </div>
                  <div className="summary-facts">
                    <span>
                      <FileText size={16} />
                      {form.invoice_number || "Number pending"}
                    </span>
                    <span>
                      <Clock3 size={16} />
                      {formatDate(form.invoice_date)}
                    </span>
                    <span>
                      {form.status === "completed" ? (
                        <CheckCircle2 size={16} />
                      ) : (
                        <AlertTriangle size={16} />
                      )}
                      {statusLabel(form.status || selected.status)}
                    </span>
                  </div>
                </section>

                <section className="panel">
                  <div className="panel-title">
                    <h3>Invoice Header</h3>
                    <StatusBadge status={form.status || selected.status} />
                  </div>
                  <div className="form-grid">
                    <Field
                      label="Invoice number"
                      value={form.invoice_number}
                      onChange={(value) =>
                        setForm({ ...form, invoice_number: value })
                      }
                    />
                    <Field
                      label="Invoice date"
                      type="date"
                      value={form.invoice_date}
                      onChange={(value) =>
                        setForm({ ...form, invoice_date: value })
                      }
                    />
                    <Field
                      label="Currency"
                      value={form.currency}
                      onChange={(value) =>
                        setForm({ ...form, currency: value })
                      }
                    />
                    <label className="field">
                      <span>Status</span>
                      <select
                        value={form.status || selected.status}
                        onChange={(event) =>
                          setForm({ ...form, status: event.target.value })
                        }
                      >
                        <option value="uploaded">uploaded</option>
                        <option value="processing">processing</option>
                        <option value="completed">completed</option>
                        <option value="needs_review">needs_review</option>
                        <option value="failed">failed</option>
                      </select>
                    </label>
                  </div>
                </section>

                <section className="panel two-column">
                  <div>
                    <h3>Seller</h3>
                    <Field
                      label="Name"
                      value={form.seller.name}
                      onChange={(value) =>
                        setPartyField("seller", "name", value)
                      }
                    />
                    <Field
                      label="Address"
                      value={form.seller.address}
                      onChange={(value) =>
                        setPartyField("seller", "address", value)
                      }
                    />
                    <Field
                      label="VAT/PAN"
                      value={form.seller.vat_pan_number}
                      onChange={(value) =>
                        setPartyField("seller", "vat_pan_number", value)
                      }
                    />
                  </div>
                  <div>
                    <h3>Buyer</h3>
                    <Field
                      label="Name"
                      value={form.buyer.name}
                      onChange={(value) =>
                        setPartyField("buyer", "name", value)
                      }
                    />
                    <Field
                      label="Address"
                      value={form.buyer.address}
                      onChange={(value) =>
                        setPartyField("buyer", "address", value)
                      }
                    />
                    <Field
                      label="VAT/PAN"
                      value={form.buyer.vat_pan_number}
                      onChange={(value) =>
                        setPartyField("buyer", "vat_pan_number", value)
                      }
                    />
                  </div>
                </section>

                <section className="panel full">
                  <div className="panel-title">
                    <h3>Line Items</h3>
                    <button className="secondary-action" onClick={addItem}>
                      Add item
                    </button>
                  </div>
                  <div className="items-table">
                    <div className="items-head">
                      <span>Description</span>
                      <span>Qty</span>
                      <span>Rate</span>
                      <span>Amount</span>
                      <span></span>
                    </div>
                    {form.items.map((item, index) => (
                      <div className="items-row" key={index}>
                        <input
                          value={item.description || ""}
                          onChange={(event) =>
                            setItemField(
                              index,
                              "description",
                              event.target.value,
                            )
                          }
                        />
                        <input
                          value={item.quantity || ""}
                          onChange={(event) =>
                            setItemField(index, "quantity", event.target.value)
                          }
                        />
                        <input
                          value={item.rate || ""}
                          onChange={(event) =>
                            setItemField(index, "rate", event.target.value)
                          }
                        />
                        <input
                          value={item.amount || ""}
                          onChange={(event) =>
                            setItemField(index, "amount", event.target.value)
                          }
                        />
                        <button
                          className="icon-button"
                          onClick={() => removeItem(index)}
                          title="Remove item"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="panel full">
                  <h3>Totals</h3>
                  <div className="form-grid totals">
                    <Field
                      label="Subtotal"
                      value={form.subtotal}
                      onChange={(value) =>
                        setForm({ ...form, subtotal: value })
                      }
                    />
                    <Field
                      label="Discount"
                      value={form.discount}
                      onChange={(value) =>
                        setForm({ ...form, discount: value })
                      }
                    />
                    <Field
                      label="VAT amount"
                      value={form.vat_amount}
                      onChange={(value) =>
                        setForm({ ...form, vat_amount: value })
                      }
                    />
                    <Field
                      label="Total amount"
                      value={form.total_amount}
                      onChange={(value) =>
                        setForm({ ...form, total_amount: value })
                      }
                    />
                  </div>
                  <label className="field wide">
                    <span>Remarks</span>
                    <textarea
                      value={form.remarks || ""}
                      onChange={(event) =>
                        setForm({ ...form, remarks: event.target.value })
                      }
                    />
                  </label>
                </section>
              </div>
            </div>
          )}
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
