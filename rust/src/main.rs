const SERVICE_STATUS: &str = r#"{"status":"ok","service":"rust-cli"}"#;

fn status_json() -> &'static str {
    SERVICE_STATUS
}

fn main() {
    println!("{}", status_json());
}

#[cfg(test)]
mod tests {
    use super::status_json;

    #[test]
    fn reports_rust_cli_status_as_json() {
        assert_eq!(status_json(), r#"{"status":"ok","service":"rust-cli"}"#);
    }
}
