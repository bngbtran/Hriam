import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { ErrorBox, PageHead } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Me } from "../../lib/types";

type Session = { access_token: string; user: Me };

function useAfterLogin() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next");
  return (s: Session) => {
    useAuth.getState().setSession(s.access_token, s.user);
    nav(next && next.startsWith("/") && !next.startsWith("//") ? next : "/");
  };
}

const loginSchema = z.object({ username: z.string().min(1, "Nhập tên đăng nhập"), password: z.string().min(1, "Nhập mật khẩu") });

export function LoginPage() {
  const done = useAfterLogin();
  const { register, handleSubmit, formState: { errors } } = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema) });
  const login = useMutation({ mutationFn: (f: z.infer<typeof loginSchema>) => api.post<Session>("/auth/login", f), onSuccess: done });
  return (
    <div className="wrap page auth">
      <PageHead eyebrow="Tài khoản" title="Đăng nhập" />
      <form className="card form" onSubmit={handleSubmit((f) => login.mutate(f))} noValidate>
        <label>Tên đăng nhập<input autoComplete="username" {...register("username")} /></label>
        {errors.username && <p className="field-error">{errors.username.message}</p>}
        <label>Mật khẩu<input type="password" autoComplete="current-password" {...register("password")} /></label>
        {errors.password && <p className="field-error">{errors.password.message}</p>}
        <ErrorBox error={login.error} />
        <button className="btn primary" disabled={login.isPending}>Đăng nhập</button>
        <p className="muted small">Chưa có tài khoản? <Link to="/register">Đăng ký</Link></p>
      </form>
    </div>
  );
}

const registerSchema = z.object({
  username: z.string().regex(/^[a-zA-Z0-9_.]{3,40}$/, "3–40 ký tự: chữ không dấu, số, dấu chấm, gạch dưới"),
  display_name: z.string().trim().min(1, "Nhập tên hiển thị").max(80),
  password: z.string().min(10, "Mật khẩu ít nhất 10 ký tự"),
  email: z.union([z.literal(""), z.string().email("Email không hợp lệ")]),
  phone: z.string().max(30),
  accept_terms: z.literal(true, { errorMap: () => ({ message: "Cần đồng ý để tiếp tục" }) }),
});
type RegisterForm = z.infer<typeof registerSchema>;

export function RegisterPage() {
  const done = useAfterLogin();
  const { register, handleSubmit, formState: { errors } } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema), defaultValues: { email: "", phone: "" },
  });
  const signup = useMutation({
    mutationFn: (f: RegisterForm) => api.post<Session>("/auth/register", { ...f, email: f.email || null, phone: f.phone || null }),
    onSuccess: done,
  });
  return (
    <div className="wrap page auth">
      <PageHead eyebrow="Tài khoản" title="Tham gia Hriăm" />
      <form className="card form" onSubmit={handleSubmit((f) => signup.mutate(f))} noValidate>
        <label>Tên đăng nhập<input autoComplete="username" {...register("username")} /></label>
        {errors.username && <p className="field-error">{errors.username.message}</p>}
        <label>Tên hiển thị<input {...register("display_name")} /></label>
        {errors.display_name && <p className="field-error">{errors.display_name.message}</p>}
        <label>Mật khẩu<input type="password" autoComplete="new-password" {...register("password")} /></label>
        {errors.password && <p className="field-error">{errors.password.message}</p>}
        <label>Email (không bắt buộc)<input type="email" autoComplete="email" {...register("email")} /></label>
        {errors.email && <p className="field-error">{errors.email.message}</p>}
        <label>Số điện thoại (không bắt buộc)<input type="tel" autoComplete="tel" {...register("phone")} /></label>
        <p className="muted small">Hriăm không lưu số điện thoại dạng rõ, chỉ lưu mã băm có khoá để chống đăng ký lại sau khi bị khoá.</p>
        <label className="check"><input type="checkbox" {...register("accept_terms")} /> Tôi đồng ý <Link to="/rules" target="_blank">quy tắc cộng đồng</Link> và <Link to="/privacy" target="_blank">chính sách quyền riêng tư</Link></label>
        {errors.accept_terms && <p className="field-error">{errors.accept_terms.message}</p>}
        <ErrorBox error={signup.error} />
        <button className="btn primary" disabled={signup.isPending}>Tạo tài khoản</button>
        <p className="muted small">Đã có tài khoản? <Link to="/login">Đăng nhập</Link></p>
      </form>
    </div>
  );
}
