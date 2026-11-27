import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";
import { useAuth } from "../auth/AuthContext";
import "./Login.css";
import illustration from "./login-illustration.png";

export const loginSchema = z.object({
  username: z.string().trim().min(1, "Identifiant requis"),
  password: z.string().min(1, "Mot de passe requis"),
});
type LoginForm = z.infer<typeof loginSchema>;
export function safeRedirect(target: unknown): string {
  return typeof target === "string" && /^\/(?![/\\])/.test(target) ? target : "/";
}
function Logo() {
  return <div className="as-logo"><svg viewBox="15 15 70 70" aria-hidden="true"><rect x="20" y="20" width="42" height="42" rx="10" fill="#a88bc4"/><rect x="38" y="38" width="42" height="42" rx="10" fill="#6d4d91"/><rect x="38" y="38" width="24" height="24" rx="5" fill="#e2d5ee"/></svg><span>AgentShield AI</span></div>;
}
export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [failed, setFailed] = useState(false);
  const [visible, setVisible] = useState(false);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });
  const destination = safeRedirect((location.state as { from?: string } | null)?.from);
  if (user) return <Navigate to={destination} replace />;
  const onSubmit = async (values: LoginForm) => {
    setFailed(false);
    try {
      await login(values.username, values.password);
      navigate(destination, { replace: true });
    } catch { setFailed(true); }
  };
  return <main className="as-login">
    <aside className="as-brand" aria-hidden="true"><img src={illustration} alt="" /></aside>
    <section className="as-form-area" aria-labelledby="login-title">
      <form className="as-form" onSubmit={handleSubmit(onSubmit)} noValidate aria-label="Connexion">
        <Logo/><h2 id="login-title">Connexion</h2>

        <label htmlFor="username">Identifiant</label>
        <input id="username" placeholder="Votre identifiant" autoComplete="username" aria-invalid={!!errors.username} aria-describedby={errors.username ? "username-error" : undefined} {...register("username")} />
        {errors.username && <p id="username-error" role="alert" className="as-field-error">{errors.username.message}</p>}
        <label htmlFor="password">Mot de passe</label>
        <div className="as-password">
          <input id="password" placeholder="Votre mot de passe" type={visible ? "text" : "password"} autoComplete="current-password" aria-invalid={!!errors.password} aria-describedby={errors.password ? "password-error" : undefined} {...register("password")} />
          <button type="button" className="as-eye" aria-label={visible?'Masquer le mot de passe':'Afficher le mot de passe'} aria-pressed={visible} onClick={()=>setVisible(v=>!v)}><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>{visible&&<path d="M3 3l18 18"/>}</svg></button>
        </div>
        {errors.password && <p id="password-error" role="alert" className="as-field-error">{errors.password.message}</p>}
        {failed && <p role="alert" className="as-error">Identifiants invalides.</p>}
        <button className="as-submit" type="submit" disabled={isSubmitting}>{isSubmitting ? "Connexion…" : "Se connecter"}<span aria-hidden="true"> →</span></button>
      </form>
    </section>
  </main>;
}
