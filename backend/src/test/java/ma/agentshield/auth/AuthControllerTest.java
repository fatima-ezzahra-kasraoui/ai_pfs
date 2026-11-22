package ma.agentshield.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import ma.agentshield.support.PostgresTestConfig;
import ma.agentshield.support.TestCredentials;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

/** AS-S1-018 : succes, echec, acces sans session -> 401, message identique, aucun mot de passe en clair. */
@SpringBootTest
@Import(PostgresTestConfig.class)
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AuthControllerTest {

    @Autowired
    private MockMvc mvc;

    @Autowired
    private UserAccountRepository users;

    @Autowired
    private PasswordEncoder encoder;

    private String rawPwd;

    @BeforeEach
    void createAnalyst() {
        users.deleteAll();
        rawPwd = TestCredentials.random();
        users.save(new UserAccount("analyste", encoder.encode(rawPwd), Role.ANALYST, "analyste@exemple.test"));
    }

    private String body(String username, String pwd) {
        return "{\"username\":\"" + username + "\",\"password\":\"" + pwd + "\"}";
    }

    private MvcResult login(String username, String pwd) throws Exception {
        return mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_JSON).content(body(username, pwd)))
                .andReturn();
    }

    @Test
    void loginSucceedsAndReturnsTheSessionUserWithoutAnySecret() throws Exception {
        MvcResult result = mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_JSON)
                        .content(body("analyste", rawPwd)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.username").value("analyste"))
                .andExpect(jsonPath("$.role").value("ANALYST"))
                .andExpect(jsonPath("$.email").value("analyste@exemple.test"))
                .andExpect(jsonPath("$.password").doesNotExist())
                .andExpect(jsonPath("$.passwordHash").doesNotExist())
                .andExpect(request().sessionAttribute("SPRING_SECURITY_CONTEXT", notNullValue()))
                .andReturn();
        assertThat(result.getResponse().getContentAsString()).doesNotContain(rawPwd).doesNotContain("$2");
    }

    @Test
    void wrongPasswordAndUnknownAccountGiveTheExactSameResponse() throws Exception {
        MvcResult wrong = login("analyste", TestCredentials.random());
        MvcResult unknown = login("inconnu", TestCredentials.random());

        assertThat(wrong.getResponse().getStatus()).isEqualTo(401);
        assertThat(unknown.getResponse().getStatus()).isEqualTo(401);
        assertThat(wrong.getResponse().getContentAsString()).isEqualTo(unknown.getResponse().getContentAsString());
        assertThat(wrong.getResponse().getContentAsString())
                .contains("INVALID_CREDENTIALS")
                .contains("Identifiants invalides.");
    }

    @Test
    void aDisabledAccountCannotLoginAndGetsTheSameGenericResponse() throws Exception {
        UserAccount account = users.findByUsername("analyste").orElseThrow();
        account.setEnabled(false);
        users.save(account);

        MvcResult result = login("analyste", rawPwd);
        assertThat(result.getResponse().getStatus()).isEqualTo(401);
        assertThat(result.getResponse().getContentAsString()).contains("INVALID_CREDENTIALS");
    }

    @Test
    void passwordIsStoredAsABcryptHash() {
        UserAccount stored = users.findByUsername("analyste").orElseThrow();
        assertThat(stored.getPasswordHash()).startsWith("$2").isNotEqualTo(rawPwd);
        assertThat(encoder.matches(rawPwd, stored.getPasswordHash())).isTrue();
    }

    @Test
    void blankCredentialsAreRejectedWith400() throws Exception {
        mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"\",\"password\":\"\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("BAD_REQUEST"));
    }

    @Test
    void meWithoutSessionIs401() throws Exception {
        mvc.perform(get("/api/auth/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.status").value(401))
                .andExpect(jsonPath("$.code").value("UNAUTHENTICATED"));
    }

    @Test
    void anyOtherApiRouteWithoutSessionIs401() throws Exception {
        mvc.perform(get("/api/dashboard/overview")).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/simulations/run").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void meWithTheSessionOfALoginReturnsTheUser() throws Exception {
        MockHttpSession session = (MockHttpSession) login("analyste", rawPwd).getRequest().getSession(false);
        assertThat(session).isNotNull();

        mvc.perform(get("/api/auth/me").session(session))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.username").value("analyste"))
                .andExpect(jsonPath("$.role").value("ANALYST"));
    }

    @Test
    void logoutEndsTheSession() throws Exception {
        MockHttpSession session = (MockHttpSession) login("analyste", rawPwd).getRequest().getSession(false);

        mvc.perform(post("/api/auth/logout").session(session)).andExpect(status().isNoContent());
        mvc.perform(get("/api/auth/me").session(session)).andExpect(status().isUnauthorized());
    }

    @Test
    void logoutWithoutSessionIs401() throws Exception {
        mvc.perform(post("/api/auth/logout")).andExpect(status().isUnauthorized());
    }

    @Test
    void loginDoesNotReuseAPreExistingSession() throws Exception {
        MockHttpSession before = new MockHttpSession();
        MvcResult result = mvc.perform(post("/api/auth/login").session(before)
                        .contentType(MediaType.APPLICATION_JSON).content(body("analyste", rawPwd)))
                .andExpect(status().isOk())
                .andReturn();

        assertThat(before.isInvalid()).isTrue();
        assertThat(result.getRequest().getSession(false)).isNotSameAs(before);
    }
}
