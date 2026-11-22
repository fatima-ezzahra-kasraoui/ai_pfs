package ma.agentshield.auth;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import ma.agentshield.support.PostgresTestConfig;
import ma.agentshield.support.TestCredentials;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;

/** Avec un vrai Tomcat : le cookie de session est HttpOnly et SameSite=Strict (MockMvc ne l'emet pas). */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Import(PostgresTestConfig.class)
@ActiveProfiles("test")
class SessionCookieTest {

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private UserAccountRepository users;

    @Autowired
    private PasswordEncoder encoder;

    @Test
    void sessionCookieIsHttpOnlyAndSameSiteStrict() {
        String pwd = TestCredentials.random();
        users.save(new UserAccount("cookie-user", encoder.encode(pwd), Role.ADMIN, null));

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        String json = "{\"username\":\"cookie-user\",\"password\":\"" + pwd + "\"}";
        ResponseEntity<String> response = rest.postForEntity("/api/auth/login", new HttpEntity<>(json, headers), String.class);

        assertThat(response.getStatusCode().is2xxSuccessful()).isTrue();
        List<String> cookies = response.getHeaders().get(HttpHeaders.SET_COOKIE);
        assertThat(cookies).isNotNull().hasSize(1);
        assertThat(cookies.get(0))
                .startsWith("AGENTSHIELD_SESSION=")
                .contains("HttpOnly")
                .contains("SameSite=Strict");
    }
}
